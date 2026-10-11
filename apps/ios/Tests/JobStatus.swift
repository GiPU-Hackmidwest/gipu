import Foundation

@main
struct JobStatusChecks {
    static func check(_ value: Bool, _ message: String = "Job status assertion failed") {
        precondition(value, message)
    }
    static func decode<T: Decodable>(_ type: T.Type, _ value: [String: Any]) throws -> T {
        try JSONDecoder().decode(type, from: JSONSerialization.data(withJSONObject: value))
    }

    static func task(_ kind: String, _ status: String, variant: Int = 0, size: Int = 512) -> [String: Any] {
        ["id": "\(kind)-\(variant)", "job_id": "job", "kind": kind, "status": status, "variant": variant,
         "width": size, "height": size, "price": 1, "progress": 0]
    }

    static func job(_ tasks: [[String: Any]], status: String = "queued", images: [[String: Any]] = []) throws -> GridJob {
        try decode(GridJob.self, ["id": "job", "owner_id": "owner", "prompt": "A cat", "status": status,
                                 "budget": 10, "spent": 0, "refunded": 0, "tasks": tasks, "images": images, "count": 1])
    }

    static func device(_ overrides: [String: Any] = [:]) throws -> Device {
        var value: [String: Any] = ["id": "worker", "owner_id": "owner", "name": "Worker", "kind": "python",
                                   "enabled": true, "online": true, "limits": ["cpu_threads": 2, "max_pixels": 262144, "session_minutes": 30],
                                   "session_expires_at": 2000, "earned": 0, "capabilities": ["image_generate"]]
        value.merge(overrides) { _, new in new }
        return try decode(Device.self, value)
    }

    static func main() throws {
        let generation = try job([task("image_generate", "queued")])
        func state(_ devices: [Device], now: Double? = 1000) -> JobStageState {
            generation.stageState("image_generate", devices: devices, serverTime: now)
        }
        check(state([]) == .unavailable)
        check(state([try device()]) == .ready)
        check(state([try device(["enabled": false])]) == .unavailable, "Paused worker was counted")
        check(state([try device(["online": false])]) == .unavailable, "Offline worker was counted")
        check(state([try device(["session_expires_at": 1000])]) == .unavailable, "Expired session was counted")
        check(state([try device(["session_expires_at": 1001])]) == .ready, "Used wall clock instead of server clock")
        check(state([try device(["capabilities": ["image_finalize"]])]) == .unavailable, "Phone was counted as generator")
        check(state([try device(["limits": ["cpu_threads": 2, "max_pixels": 65536, "session_minutes": 30]])]) == .unavailable)
        check(state([try device(["active_task_id": "other-job"] )]) == .busy)
        check(state([try device(["active_task_id": "other-job"]), try device()]) == .ready)
        check(state([try device()], now: nil) == .unknown, "Missing server time became a capacity claim")
        check(state([try device(["session_expires_at": NSNull()])]) == .unknown)
        check(state([try device(["capabilities": NSNull()])]) == .unknown)
        check(state([try device(["active_task_id": "other"]), try device(["capabilities": NSNull()])]) == .unknown)
        check(try job([task("image_generate", "running")], status: "running").stageState("image_generate", devices: [], serverTime: 1000) == .running)
        check(generation.stageState("image_finalize", devices: [], serverTime: 1000) == .waitingForGeneration)

        let preview: [String: Any] = ["task_id": "g", "url": "/api/images/g", "variant": 0, "stage": "image_generate"]
        let exported: [String: Any] = ["task_id": "f", "url": "/api/images/f", "variant": 0, "stage": "image_finalize"]
        let finishing = try job([task("image_generate", "completed"), task("image_finalize", "queued")], status: "running", images: [preview])
        let phone = try device(["kind": "ios", "enabled": false, "capabilities": ["image_finalize"]])
        check(finishing.completedCount("image_generate") == 1 && finishing.completedCount("image_finalize") == 0)
        check(finishing.stageState("image_generate", devices: [], serverTime: 1000) == .complete)
        check(finishing.stageState("image_finalize", devices: [phone], serverTime: 1000) == .unavailable)
        check(finishing.canStartFinishing(on: phone, limits: Limits()), "Eligible paused phone lacked Start action")
        check(!finishing.canStartFinishing(on: phone, limits: Limits(max_pixels: 65536)), "CTA would exceed selected limit")
        check(!generation.canStartFinishing(on: phone, limits: Limits()), "CTA shown without finishing work")
        check(!finishing.canStartFinishing(on: try device(), limits: Limits()), "CTA shown for a generator")
        check(!finishing.canStartFinishing(on: try device(["kind": "ios", "online": false, "capabilities": ["image_finalize"]]), limits: Limits()))
        check(!finishing.canStartFinishing(on: try device(["kind": "ios", "active_task_id": "other", "capabilities": ["image_finalize"]]), limits: Limits()))
        check(finishing.displayImages.count == 1 && finishing.displayImages[0].stage == "image_generate")
        let done = try job([task("image_generate", "completed"), task("image_finalize", "completed")], status: "completed", images: [preview, exported])
        check(done.displayImages.count == 1 && done.displayImages[0].stage == "image_finalize", "Preview obscures the finished output")
        check(done.stageState("image_finalize", devices: [], serverTime: nil) == .complete)
        check(!done.canStartFinishing(on: phone, limits: Limits()))
        let cancelled = try job([task("image_generate", "completed"), task("image_finalize", "cancelled")], status: "cancelled")
        check(cancelled.stageState("image_finalize", devices: [], serverTime: 1000) == .stopped)
        check(!cancelled.canStartFinishing(on: phone, limits: Limits()))

        let legacy = try decode(GridJob.self, ["id": "old", "owner_id": "owner", "prompt": "cat", "status": "queued",
                                               "budget": 10, "spent": 0, "refunded": 0, "images": [],
                                               "tasks": [task("image_generate", "queued"), task("image_generate", "queued", variant: 1)]])
        check(legacy.imageCount == 2, "Older snapshots lost the count fallback")
        let snapshot = try decode(Snapshot.self, ["user": ["id": "owner", "name": "Test"], "balance": 10, "reserved": 0, "earned": 0,
                                                 "devices": [], "jobs": [], "events": [], "agent": ["mode": "manual", "available": false]])
        check(snapshot.server_time == nil, "Older snapshots must still decode")
        print("PASS: job stages, session expiry, capability/size/busy checks, safe Start CTA, preview/export selection and older snapshots")
    }
}
