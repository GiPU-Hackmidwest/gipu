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
struct GridJob: Decodable, Identifiable {
    let id: String; let owner_id: String; let prompt: String; let status: String; let budget: Int
    let spent: Int; let refunded: Int; let tasks: [GridTask]; let images: [JobImage]; let receipt: Receipt?
}
struct GridEvent: Decodable, Identifiable {
    let id: Int; let kind: String; let message: String; let created_at: Double; let device_id: String?
}
struct AgentStatus: Decodable { let mode: String; let available: Bool }
struct Snapshot: Decodable {
    let user: GridUser; let balance: Int; let reserved: Int; let earned: Int
    let devices: [Device]; let jobs: [GridJob]; let events: [GridEvent]; let agent: AgentStatus
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
        // Agent planning may exceed the normal control-request timeout.
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
