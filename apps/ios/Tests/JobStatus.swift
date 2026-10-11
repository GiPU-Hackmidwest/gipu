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

    static func job(_ tasks: [[String: Any]], status: String = "queued", images: [[String: Any]] = [], overrides: [String: Any] = [:]) throws -> GridJob {
        var value: [String: Any] = ["id": "job", "owner_id": "owner", "prompt": "A cat", "status": status,
                                   "budget": 10, "spent": 0, "refunded": 0, "tasks": tasks, "images": images, "count": 1]
        value.merge(overrides) { _, new in new }
        return try decode(GridJob.self, value)
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

        let pendingPlan: [String: Any] = ["mode": "strands-ollama", "planning": ["status": "pending", "attempts": 0]]
        let runningPlan: [String: Any] = ["mode": "strands-ollama", "planning": ["status": "running", "attempts": 1, "claim_id": "server-only-claim", "started_at": 1000]]
        let planning = try job([], status: "planning", overrides: ["reserved": 10, "plan": pendingPlan])
        check(planning.isPlanning && planning.isActive, "Acknowledged planning request must be cancellable")
        check(planning.planningTitle == "Waiting for the planner")
        check(planning.stageState("image_generate", devices: [], serverTime: 1000) == .planning, "Empty planning tasks became unavailable capacity")
        check(planning.stageState("image_finalize", devices: [], serverTime: 1000) == .planning, "Planning became a finishing queue")
        check(!planning.canStartFinishing(on: phone, limits: Limits()), "Planning must not suggest starting a phone")
        check(planning.submissionAcknowledgement.contains("saved") && planning.submissionAcknowledgement.contains("10 credits reserved"))
        let selecting = try job([], status: "planning", overrides: ["reserved": 9, "plan": runningPlan])
        check(selecting.planningTitle == "Planning your request")
        check(selecting.reservedCredits == 9 && selecting.planningMessage.contains("9 credits"), "UI must prefer server-reported reservation")

        let fullReceipt: [String: Any] = ["budget": 10, "contributor_total": 0, "platform_fee": 0, "refund": 10, "total_charged": 0]
        let failedPlan: [String: Any] = ["mode": "strands-ollama", "planning": ["status": "failed"], "dispatch_error": "TimeoutError"]
        let planningFailure = try job([], status: "failed", overrides: ["plan": failedPlan, "refunded": 10, "reserved": 0, "receipt": fullReceipt])
        check(planningFailure.failedDuringPlanning && !planningFailure.isActive)
        check(planningFailure.statusLabel == "Planning failed")
        check(planningFailure.fullRefundConfirmed && planningFailure.terminalSummary?.contains("full budget of 10") == true)
        var mismatchedBudget = fullReceipt
        mismatchedBudget["budget"] = 11
        check(try !job([], status: "failed", overrides: ["plan": failedPlan, "receipt": mismatchedBudget]).fullRefundConfirmed,
              "Receipt budget must match the request before claiming a full refund")
        var nonzeroCharge = fullReceipt
        nonzeroCharge["total_charged"] = 1
        check(try !job([], status: "failed", overrides: ["plan": failedPlan, "receipt": nonzeroCharge]).fullRefundConfirmed,
              "A charged receipt must not claim a full refund")
        let unconfirmedRefund = try job([], status: "failed", overrides: ["plan": failedPlan, "refunded": 10])
        check(!unconfirmedRefund.fullRefundConfirmed && unconfirmedRefund.terminalSummary?.contains("full budget") == false,
              "Refund total alone must not establish a fully refunded receipt")
        let chargedReceipt: [String: Any] = ["budget": 10, "contributor_total": 6, "platform_fee": 0, "refund": 4, "total_charged": 6]
        let afterPlanning = try job([task("image_generate", "completed"), task("image_finalize", "cancelled")], status: "failed",
                                   overrides: ["plan": ["planning": ["status": "done"], "dispatch_error": "LaterReviewError"], "spent": 6, "refunded": 4, "receipt": chargedReceipt])
        check(!afterPlanning.failedDuringPlanning && !afterPlanning.fullRefundConfirmed,
              "A later processing failure must not be labeled as a planning failure/full refund")
        check(afterPlanning.terminalSummary?.contains("4 credits returned") == true)
        check(try job([], status: "failed").failedDuringPlanning == false, "Empty legacy tasks do not prove planning failed")
        let cancelledPlanning = try job([], status: "cancelled", overrides: ["plan": runningPlan, "refunded": 10, "receipt": fullReceipt])
        check(cancelledPlanning.cancelledDuringPlanning && !cancelledPlanning.isActive)
        check(cancelledPlanning.statusLabel == "Planning cancelled" && cancelledPlanning.fullRefundConfirmed)
        let oldSync = try job([task("image_generate", "queued")], overrides: ["plan": ["mode": "strands-ollama", "explanation": "Selected devices"]])
        let readyGenerator = try device()
        check(!oldSync.isPlanning && oldSync.stageState("image_generate", devices: [readyGenerator], serverTime: 1000) == .ready,
              "Older synchronous Strands responses must keep working")

        // POST succeeds, then GET /state fails or an older in-flight snapshot
        // arrives: the saved job must remain visible with its Cancel action.
        var acknowledged = AcknowledgedJobs()
        let beforePOST = acknowledged.revision
        acknowledged.retain(planning)
        check(acknowledged.merged(with: []).first?.isActive == true, "Refresh failure hid an accepted planning request")
        acknowledged.reconcile([], requestedAt: acknowledged.revision)
        check(acknowledged.jobs.count == 1, "Snapshot missing the job erased its acknowledgment")
        acknowledged.reconcile([planning], requestedAt: beforePOST)
        check(acknowledged.jobs.count == 1, "A pre-POST snapshot erased the retained acknowledgment")
        let beforeCancel = acknowledged.revision
        acknowledged.retain(cancelledPlanning)
        acknowledged.reconcile([planning], requestedAt: beforeCancel)
        check(acknowledged.merged(with: [planning]).first?.status == "cancelled", "A stale snapshot revived a cancelled request")
        acknowledged.reconcile([cancelledPlanning], requestedAt: acknowledged.revision)
        check(acknowledged.jobs.isEmpty && acknowledged.merged(with: [cancelledPlanning]).count == 1,
              "A fresh snapshot should replace the retained acknowledgment without duplicate cards")

        // Reproduce the late pre-cancel response after a fresh snapshot already
        // removed the retained cancellation. The entire old snapshot is rejected.
        var cache = AcknowledgedJobs()
        var gate = SnapshotGate()
        cache.retain(planning)
        let stale = gate.begin(acknowledgmentRevision: cache.revision)
        cache.retain(cancelledPlanning)
        let fresh = gate.begin(acknowledgmentRevision: cache.revision)
        var displayed = [planning]
        if gate.accept(fresh, acknowledgmentRevision: cache.revision) {
            displayed = [cancelledPlanning]
            cache.reconcile(displayed, requestedAt: fresh.acknowledgmentRevision)
        }
        check(cache.jobs.isEmpty)
        if gate.accept(stale, acknowledgmentRevision: cache.revision) { displayed = [planning] }
        check(displayed.first?.status == "cancelled", "Late snapshot revived a cancelled job after cache reconciliation")
        let earlier = gate.begin(acknowledgmentRevision: cache.revision)
        let later = gate.begin(acknowledgmentRevision: cache.revision)
        check(gate.accept(later, acknowledgmentRevision: cache.revision))
        check(!gate.accept(earlier, acknowledgmentRevision: cache.revision), "Out-of-order responses with the same acknowledgment revision must be fenced")
        let preMutation = gate.begin(acknowledgmentRevision: cache.revision)
        cache.retain(planningFailure)
        check(!gate.accept(preMutation, acknowledgmentRevision: cache.revision), "A pre-acknowledgment snapshot must be rejected even before a newer fetch completes")
        print("PASS: async planning/cancellation/refunds, full-snapshot ordering, accepted-response retention, job stages, safe Start CTA and older snapshots")
    }
}
