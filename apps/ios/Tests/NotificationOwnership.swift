import Foundation

@main
struct NotificationOwnership {
    static func main() throws {
        let userID = "requester"
        let deviceID = "phone"
        var checks = 0

        func event(_ kind: String, owner: Any? = nil, device: Any? = nil) throws -> GridEvent {
            var payload: [String: Any] = ["id": 1, "kind": kind, "message": "Activity", "created_at": 1]
            if let owner { payload["user_id"] = owner }
            if let device { payload["device_id"] = device }
            return try JSONDecoder().decode(GridEvent.self, from: JSONSerialization.data(withJSONObject: payload))
        }

        func expect(_ event: GridEvent, _ expected: Bool, _ message: String, currentUser: String = "requester") {
            precondition(event.shouldNotify(userID: currentUser, deviceID: deviceID) == expected, message)
            checks += 1
        }

        // State includes a requester's jobs, including credits paid to other owners.
        expect(try event("credits_earned", owner: "contributor"), false, "Another contributor's earnings were attributed to the requester")
        expect(try event("credits_earned", owner: "contributor", device: deviceID), false, "A matching device must not override the recipient")
        expect(try event("credits_earned"), false, "Missing recipient must not imply current-user earnings")
        expect(try event("credits_earned", owner: NSNull()), false, "Null recipient must not imply current-user earnings")
        expect(try event("credits_earned", owner: ""), false, "Empty recipient must not imply current-user earnings")
        expect(try event("credits_earned", owner: ""), false, "An unknown current user must not match an empty recipient", currentUser: "")
        expect(try event("credits_earned", owner: userID), true, "Explicit personal earnings without a device were suppressed")
        expect(try event("credits_earned", owner: userID, device: NSNull()), true, "Explicit personal earnings with a null device were suppressed")
        expect(try event("credits_earned", owner: userID, device: deviceID), true, "This phone's personal earnings were suppressed")
        expect(try event("credits_earned", owner: userID, device: "laptop"), false, "Existing device filtering changed")

        // Task/job notifications retain their existing kind and device rules.
        expect(try event("task_started", device: deviceID), true, "This phone's task notification changed")
        expect(try event("task_started", owner: "contributor"), true, "Device-less task notification changed")
        expect(try event("task_started", owner: userID, device: "laptop"), false, "Other-device task notification changed")
        expect(try event("job_completed"), true, "Public job completion notification changed")
        expect(try event("job_completed", owner: "contributor", device: deviceID), true, "Recipient filter leaked into job notifications")
        expect(try event("job_completed", device: "laptop"), false, "Other-device job notification changed")
        expect(try event("device_paused", owner: userID, device: deviceID), false, "An unrelated event began notifying")
        print("PASS: \(checks) notification recipient, decoding, and existing task/job behavior checks")
    }
}
