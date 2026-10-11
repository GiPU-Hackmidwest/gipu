import Foundation

@main
struct IdentityPrivacyChecks {
    static func main() throws {
        let link = GridLink(kind: .link, server: "https://grid.example", code: "ABCD234567")
        precondition(GridLink.parse(link.payload) == link)
        precondition(GridLink.parse("gipu://link?grid=https%3A%2F%2Fgrid.example%2F&code=abcd-234567") == link)
        let invite = GridLink(kind: .join, server: "http://127.0.0.1:8787", code: "with + & symbols")
        precondition(GridLink.parse(invite.payload) == invite)
        for payload in ["https://grid.example", "gipu://unknown?grid=https://grid.example&code=x",
                        "gipu://link?grid=https://grid.example&code=ABCDEFGHIJ", "gipu://link?grid=https://grid.example&code=ABC",
                        "gipu://join?grid=javascript:alert(1)&code=x", "gipu://join?grid=https://user:secret@grid.example&code=x",
                        "gipu://join?grid=https://grid.example/path&code=x", "gipu://join?grid=https://grid.example%3Fx=y&code=x",
                        "gipu://join?grid=https://grid.example&code=", "gipu://join?code=secret"] {
            precondition(GridLink.parse(payload) == nil, "Unsafe/malformed link accepted")
        }
        precondition(GridLink.normalizeServer(" https://grid.example/// ") == "https://grid.example")
        precondition(GridLink.normalizeServer("HTTPS://GRID.EXAMPLE") == "HTTPS://GRID.EXAMPLE")
        precondition(GridLink.normalizeServer("https://grid.example#fragment") == nil)
        precondition(GridLink.normalizeServer("file:///tmp") == nil)
        func decode<T: Decodable>(_ type: T.Type, _ object: [String: Any]) throws -> T {
            try JSONDecoder().decode(type, from: JSONSerialization.data(withJSONObject: object))
        }
        let oldSession = try decode(SessionReply.self, ["token":"dummy", "user":["id":"me", "name":"Guest"], "balance":100])
        precondition(oldSession.session_id == nil && oldSession.user.username == nil)
        let newSession = try decode(SessionReply.self, ["token":"dummy", "session_id":"session", "user":["id":"me", "name":"Guest", "username":"name"], "balance":37])
        precondition(newSession.session_id == "session" && newSession.balance == 37)
        let limits: [String: Any] = ["cpu_threads":1, "max_pixels":65536, "session_minutes":30]
        func device(_ owner: String) -> [String: Any] {
            ["id":owner + "-device", "owner_id":owner, "name":owner + "-private-name", "kind":"ios", "enabled":false, "online":true, "limits":limits, "earned":0]
        }
        func job(_ owner: String) -> [String: Any] {
            ["id":owner + "-job", "owner_id":owner, "prompt":owner + "-private-prompt", "status":"queued", "budget":10, "spent":0, "refunded":0, "tasks":[], "images":[]]
        }
        func event(_ id: Int, _ kind: String, owner: String? = nil, job: String? = nil) -> [String: Any] {
            var value: [String: Any] = ["id":id, "kind":kind, "message":"Foreign name ID secret prompt", "created_at":1]
            if let owner { value["user_id"] = owner }; if let job { value["job_id"] = job }
            return value
        }
        let payload: [String: Any] = ["user":["id":"me", "name":"Me"], "balance":100, "reserved":0, "earned":0,
                                     "devices":[device("me"), device("other")], "jobs":[job("me"), job("other")],
                                     "events":[event(1,"job_completed",job:"me-job"), event(2,"job_completed",job:"other-job"),
                                               event(3,"credits_earned",owner:"other",job:"me-job"), event(4,"credits_earned",owner:"me"),
                                               event(5,"task_started"), event(6,"routing_updated",job:"me-job")],
                                     "agent":["mode":"manual", "available":false]]
        let state = try decode(Snapshot.self, payload)
        precondition(state.grid == nil, "Missing counts must remain unknown")
        precondition(state.ownDevices.map(\.id) == ["me-device"] && state.ownJobs.map(\.id) == ["me-job"])
        precondition(state.ownEvents.map(\.id) == [1,4,6])
        precondition(state.ownEvents.allSatisfy { !($0.safeMessage ?? "").contains("secret") })
        let ownCompletion = try decode(GridEvent.self, ["id":7, "kind":"job_completed", "message":"private", "created_at":1,
                                                        "job_id":"me-job", "device_id":"another-owned-device"])
        precondition(ownCompletion.shouldNotifyScoped(userID:"me",deviceID:"me-device",ownJobs:["me-job"],ownDevices:["me-device","another-owned-device"]))
        let foreignCompletion = try decode(GridEvent.self, ["id":8, "kind":"job_completed", "message":"private", "created_at":1,
                                                            "job_id":"other-job", "device_id":"me-device"])
        precondition(!foreignCompletion.isVisible(userID:"me",ownJobs:["me-job"],ownDevices:["me-device"]))
        precondition(!foreignCompletion.shouldNotifyScoped(userID:"me",deviceID:"me-device",ownJobs:["me-job"],ownDevices:["me-device"]))
        for (value, expected) in [(false, "false"), (true, "true")] {
            let image = try decode(JobImage.self,["task_id":"t", "url":"/api/images/x", "variant":0, "stage":"image_finalize", "verified":value])
            precondition(image.verified?.description == expected)
        }
        let legacy = try decode(JobImage.self,["task_id":"t", "url":"/api/images/x", "variant":0, "stage":"image_finalize"])
        precondition(legacy.verified == nil, "Legacy finalization must not imply a verified field")
        print("PASS: link parsing/normalization, rejected unsafe origins, legacy/V1 account decoding, own-only data and generic activity, verified tri-state")
    }
}
