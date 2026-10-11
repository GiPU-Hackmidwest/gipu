import Foundation

struct GridUser: Decodable { let id: String; let name: String }
struct SessionReply: Decodable { let token: String; let user: GridUser; let balance: Int }
struct Limits: Codable, Equatable {
    var cpu_threads: Int = 1
    var max_pixels: Int = 262144
    var session_minutes: Int = 30
}
struct Telemetry: Decodable { let progress: Double?; let stage: String?; let backend: String? }
struct Device: Decodable, Identifiable {
    let id: String; let owner_id: String; let name: String; let kind: String
    let enabled: Bool; let online: Bool; let limits: Limits
    let session_expires_at: Double?; let active_task_id: String?; let telemetry: Telemetry?; let earned: Int
    let capabilities: [String]?
}
struct DeviceReply: Decodable { let device: Device; let token: String }
struct HeartbeatReply: Decodable { let device: Device; let lease_valid: Bool }
struct ClaimReply: Decodable { let task: GridTask?; let device: Device }
struct GridTask: Decodable, Identifiable {
    let id: String; let job_id: String; let kind: String; let status: String; let variant: Int
    let width: Int; let height: Int; let price: Int; let lease_id: String?; let source_url: String?; let progress: Double
}
struct JobImage: Decodable, Identifiable {
    var id: String { task_id + stage }
    let task_id: String; let url: String; let variant: Int; let stage: String
}
struct Receipt: Decodable {
    let budget: Int; let contributor_total: Int; let platform_fee: Int; let refund: Int; let total_charged: Int
}
struct JobPlanning: Decodable { let status: String? }
struct JobPlan: Decodable {
    let planning: JobPlanning?
}
struct GridJob: Decodable, Identifiable {
    let id: String; let owner_id: String; let prompt: String; let status: String; let budget: Int
    let spent: Int; let refunded: Int; let tasks: [GridTask]; let images: [JobImage]; let receipt: Receipt?
    let count: Int?
    let reserved: Int?
    let plan: JobPlan?
}
struct GridEvent: Decodable, Identifiable {
    let id: Int; let kind: String; let message: String; let created_at: Double; let device_id: String?
    let user_id: String?

    func shouldNotify(userID: String, deviceID: String) -> Bool {
        guard ["task_started", "credits_earned", "job_completed"].contains(kind),
              device_id == nil || device_id == deviceID else { return false }
        // Requesters also receive other contributors' earning events in activity.
        // Only an explicit recipient match makes this a personal earnings alert.
        return kind != "credits_earned" || (!userID.isEmpty && user_id == userID)
    }
}
struct AgentStatus: Decodable { let mode: String; let available: Bool }
struct Snapshot: Decodable {
    let user: GridUser; let balance: Int; let reserved: Int; let earned: Int
    let devices: [Device]; let jobs: [GridJob]; let events: [GridEvent]; let agent: AgentStatus
    let server_time: Double?
}

/// Describes observed queue capacity, not a guarantee of the next assignment.
/// The server also enforces routing preferences and retry exclusions.
enum JobStageState: Equatable {
    case planning, running, complete, waitingForGeneration, ready, busy, unavailable, unknown, stopped

    func message(for kind: String) -> String {
        let generation = kind == "image_generate"
        switch self {
        case .planning: return "Device selection is being planned. No image work is queued yet."
        case .running: return generation ? "Generating on a participating laptop." : "A participating device is finishing the export."
        case .complete: return generation ? "Image generation is complete." : "Finished images are ready."
        case .waitingForGeneration: return "Finishing starts when a generated image is ready."
        case .ready: return generation ? "Waiting for a compatible laptop to accept work." : "Waiting for a compatible device to accept finishing work."
        case .busy: return generation ? "Compatible sharing laptops are busy. This request is queued." : "Compatible sharing devices are busy. Finishing is queued."
        case .unavailable: return generation ? "No laptop is available within this request’s image limits. Start or renew sharing on a compatible laptop." : "No device is available within this request’s image limits. Start or renew sharing on a compatible device."
        case .unknown: return "Checking task readiness and device availability."
        case .stopped: return "No further work will run for this request."
        }
    }
}

extension GridJob {
    var isPlanning: Bool { status == "planning" }
    var isActive: Bool { ["planning", "queued", "running"].contains(status) }
    var reservedCredits: Int { max(0, reserved ?? (budget - spent - refunded)) }
    // Empty tasks alone do not establish a planning failure on older servers.
    var failedDuringPlanning: Bool {
        status == "failed" && plan?.planning?.status == "failed"
    }
    var cancelledDuringPlanning: Bool {
        status == "cancelled" && tasks.isEmpty && plan?.planning != nil && plan?.planning?.status != "done"
    }
    var statusLabel: String {
        if failedDuringPlanning { return "Planning failed" }
        if cancelledDuringPlanning { return "Planning cancelled" }
        return status.capitalized
    }
    var planningMessage: String {
        let action = plan?.planning?.status == "running"
            ? "Strands is choosing compatible devices."
            : "Waiting for Strands to plan this request."
        return "\(action) No image work is queued yet. \(reservedCredits) credits are reserved. You can cancel while planning."
    }
    var planningTitle: String {
        plan?.planning?.status == "pending" ? "Waiting for the planner" : "Planning your request"
    }
    var fullRefundConfirmed: Bool {
        guard let receipt else { return false }
        return receipt.budget == budget && receipt.contributor_total == 0 && receipt.platform_fee == 0
            && receipt.refund == budget && receipt.total_charged == 0
    }
    var terminalSummary: String? {
        let outcome: String
        switch status {
        case "failed" where failedDuringPlanning:
            outcome = tasks.isEmpty ? "Planning failed before image work was queued." : "Planning did not complete."
        case "failed":
            outcome = "Image processing did not complete."
        case "cancelled" where cancelledDuringPlanning:
            outcome = "Cancelled before image work was queued."
        case "cancelled":
            outcome = "Request cancelled. Previously accepted work remains paid."
        default: return nil
        }
        // Display settled accounting, rather than promising a full refund for
        // an execution failure that may already have paid contributors.
        if fullRefundConfirmed { return "\(outcome) Your full budget of \(budget) credits was returned." }
        return "\(outcome) \(receipt?.refund ?? refunded) credits returned. Check the receipt for charges."
    }
    var submissionAcknowledgement: String {
        switch status {
        case "planning": return "Request saved with \(reservedCredits) credits reserved. Follow planning below."
        case "queued": return "Request saved and queued with \(reservedCredits) credits reserved."
        case "running": return "Request saved. Image processing is underway; follow its progress below."
        case "completed": return "Request completed. Its images and receipt are below."
        case "failed", "cancelled": return terminalSummary ?? "Check the request status below."
        default: return "Request saved. Follow its status below."
        }
    }
    var imageCount: Int { count ?? Set(tasks.filter { $0.kind == "image_generate" }.map(\.variant)).count }
    func completedCount(_ kind: String) -> Int { tasks.filter { $0.kind == kind && $0.status == "completed" }.count }

    func stageState(_ kind: String, devices: [Device], serverTime: Double?) -> JobStageState {
        if isPlanning { return .planning }
        let stageTasks = tasks.filter { $0.kind == kind }
        if imageCount > 0 && completedCount(kind) == imageCount { return .complete }
        if ["completed", "cancelled", "failed"].contains(status) { return .stopped }
        guard isActive else { return .unknown }
        if stageTasks.contains(where: { $0.status == "running" }) { return .running }
        let queued = stageTasks.filter { $0.status == "queued" }
        if queued.isEmpty { return kind == "image_finalize" ? .waitingForGeneration : .unknown }

        var hasBusyCapacity = false
        var missingEvidence = false
        for task in queued {
            for device in devices where device.online && device.enabled && task.width * task.height <= device.limits.max_pixels {
                guard let capabilities = device.capabilities else { missingEvidence = true; continue }
                guard capabilities.contains(kind) else { continue }
                guard let now = serverTime, let expiry = device.session_expires_at else { missingEvidence = true; continue }
                guard expiry > now else { continue }
                if device.active_task_id == nil { return .ready }
                hasBusyCapacity = true
            }
        }
        if missingEvidence { return .unknown }
        return hasBusyCapacity ? .busy : .unavailable
    }

    func canStartFinishing(on device: Device?, limits: Limits) -> Bool {
        guard isActive, !isPlanning, let device, device.online, device.active_task_id == nil,
              device.capabilities?.contains("image_finalize") == true else { return false }
        return tasks.contains { $0.kind == "image_finalize" && $0.status == "queued" && $0.width * $0.height <= limits.max_pixels }
    }

    /// Show the accepted export when available, otherwise label the generation preview.
    var displayImages: [JobImage] {
        let grouped = Dictionary(grouping: images, by: \.variant)
        let selected: [JobImage] = grouped.values.compactMap { variants in
            if let finished = variants.first(where: { $0.stage == "image_finalize" }) { return finished }
            if let generated = variants.first(where: { $0.stage == "image_generate" }) { return generated }
            return variants.first
        }
        return selected.sorted { $0.variant < $1.variant }
    }
}

/// Keep an acknowledged job visible and cancellable even when the following
/// snapshot fails. A snapshot started before that acknowledgment cannot erase it.
struct AcknowledgedJobs {
    private(set) var jobs: [GridJob] = []
    private(set) var revision = 0

    mutating func retain(_ job: GridJob) {
        jobs.removeAll { $0.id == job.id }
        jobs.insert(job, at: 0)
        revision += 1
    }
    mutating func reconcile(_ snapshot: [GridJob], requestedAt revision: Int) {
        guard revision == self.revision else { return }
        let confirmed = Set(snapshot.map(\.id))
        jobs.removeAll { confirmed.contains($0.id) }
    }
    func merged(with snapshot: [GridJob]) -> [GridJob] {
        let retained = Set(jobs.map(\.id))
        return jobs + snapshot.filter { !retained.contains($0.id) }
    }
}

struct SnapshotRequest {
    let sequence: Int
    let acknowledgmentRevision: Int
}

/// Fence the entire snapshot, including balances and jobs, after a newer
/// acknowledgment or successfully applied response has made it obsolete.
struct SnapshotGate {
    private var issued = 0
    private var applied = 0
    mutating func begin(acknowledgmentRevision: Int) -> SnapshotRequest {
        issued += 1
        return SnapshotRequest(sequence: issued, acknowledgmentRevision: acknowledgmentRevision)
    }
    func isCurrent(_ request: SnapshotRequest, acknowledgmentRevision: Int) -> Bool {
        request.sequence > applied && request.acknowledgmentRevision == acknowledgmentRevision
    }
    mutating func accept(_ request: SnapshotRequest, acknowledgmentRevision: Int) -> Bool {
        guard isCurrent(request, acknowledgmentRevision: acknowledgmentRevision) else { return false }
        applied = request.sequence
        return true
    }
}

enum APIError: LocalizedError {
    case invalidURL, server(Int, String)
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Enter the coordinator URL, including http:// or https://."
        case let .server(status, detail): return "Server \(status): \(detail)"
        }
    }
}

struct GridAPI {
    let server: String
    private static let session = URLSession(configuration: .ephemeral)
    func data(_ path: String, token: String?, method: String = "GET", body: [String: Any]? = nil) async throws -> Data {
        guard let base = URL(string: server), let scheme = base.scheme,
              ["http", "https"].contains(scheme), base.host != nil,
              let url = URL(string: path, relativeTo: base)?.absoluteURL,
              url.host == base.host, url.scheme == base.scheme, url.port == base.port else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        // Older coordinators plan synchronously; current ones acknowledge
        // durable planning promptly. Keep compatibility with both contracts.
        request.timeoutInterval = (method == "POST" && path == "/api/jobs") ? 180 : 20
        request.httpMethod = method
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let (data, response) = try await Self.session.data(for: request)
        guard let response = response as? HTTPURLResponse, (200..<300).contains(response.statusCode) else {
            throw APIError.server((response as? HTTPURLResponse)?.statusCode ?? 0,
                                  String(data: data, encoding: .utf8)?.prefix(400).description ?? "Request failed")
        }
        return data
    }
    func json<T: Decodable>(_ type: T.Type, _ path: String, token: String?, method: String = "GET", body: [String: Any]? = nil) async throws -> T {
        try JSONDecoder().decode(type, from: await data(path, token: token, method: method, body: body))
    }
}

extension Limits {
    var dictionary: [String: Any] { ["cpu_threads": cpu_threads, "max_pixels": max_pixels, "session_minutes": session_minutes] }
}

/// Fences asynchronous replies from a previous contribution session. A stopped
/// Start request cannot become valid again merely because the app foregrounds.
struct ContributionGate {
    private(set) var generation = 0
    private var starts = 0
    private var pauses = 0
    var transitioning: Bool { starts > 0 || pauses > 0 }
    mutating func beginStart() -> Int? {
        guard !transitioning else { return nil }
        generation += 1
        starts += 1
        return generation
    }
    mutating func finishStart() { starts -= 1 }
    mutating func beginPause() { pauses += 1; invalidate() }
    mutating func finishPause() { pauses -= 1 }
    mutating func invalidate() { generation += 1 }
    func permits(_ ticket: Int, foreground: Bool) -> Bool { ticket == generation && foreground }
}
