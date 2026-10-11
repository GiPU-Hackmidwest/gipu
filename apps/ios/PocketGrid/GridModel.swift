import Foundation
import SwiftUI
import Combine
import Security
import UserNotifications

private struct SavedSession: Codable {
    let server: String; let token: String; let deviceID: String; let deviceToken: String
}

private enum SessionStore {
    static let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                      kSecAttrService as String: "com.pocketgrid.prototype",
                                      kSecAttrAccount as String: "grid-session"]
    static func load() -> Data? {
        var match = query
        match[kSecReturnData as String] = true
        match[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        guard SecItemCopyMatching(match as CFDictionary, &result) == errSecSuccess else { return nil }
        return result as? Data
    }
    static func save(_ data: Data?) {
        SecItemDelete(query as CFDictionary)
        guard let data else { return }
        var item = query
        item[kSecValueData as String] = data
        item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(item as CFDictionary, nil)
    }
}

@MainActor
final class GridModel: ObservableObject {
    @Published var server = "http://127.0.0.1:8787"
    @Published var name = "My iPhone"
    @Published var joinCode = "pocketgrid-demo"
    @Published var connected = false
    @Published var busy = false
    @Published private(set) var submitting = false
    @Published var error: String?
    @Published var notice: String?
    @Published var snapshot: Snapshot?
    @Published var limits = Limits()
    @Published var sharing = false
    @Published var active: GridTask?
    @Published var progress = 0.0
    @Published var stage = "Paused"
    @Published var notificationStatus = "Off"
    @Published private(set) var contributionTransition = false
    @Published private var acknowledgedJobs = AcknowledgedJobs()

    private var pendingSubmission: (signature: Data, id: String)?
    private var token = ""
    private var deviceID = ""
    private var deviceToken = ""
    private var pollTask: Task<Void, Never>?
    private var heartbeatTask: Task<Void, Never>?
    private var workerTask: Task<Void, Never>?
    private var renderTask: Task<Data, Error>?
    private var seenEvents = Set<Int>()
    private var didLoadEvents = false
    private var foreground = true
    private var contributionGate = ContributionGate()
    private var snapshotGate = SnapshotGate()
    var api: GridAPI { GridAPI(server: server) }
    var ownDevice: Device? { snapshot?.devices.first { $0.id == deviceID } }
    var ownJobs: [GridJob] {
        acknowledgedJobs.merged(with: snapshot?.jobs.filter { $0.owner_id == snapshot?.user.id } ?? [])
    }

    init() {
        guard let data = SessionStore.load(), let saved = try? JSONDecoder().decode(SavedSession.self, from: data) else { return }
        server = saved.server; token = saved.token; deviceID = saved.deviceID; deviceToken = saved.deviceToken
        connected = true
        contributionTransition = true
        Task {
            // A relaunch never silently resumes contributed work.
            await pause()
            await refresh()
            if let device = ownDevice { limits = device.limits }
            startLoops()
        }
    }

    func join() async {
        busy = true; error = nil
        defer { busy = false }
        do {
            server = server.trimmingCharacters(in: .whitespacesAndNewlines).trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            let reply = try await api.json(SessionReply.self, "/api/sessions", token: nil, method: "POST",
                                           body: ["name": name, "join_code": joinCode])
            let device = try await api.json(DeviceReply.self, "/api/devices", token: reply.token, method: "POST",
                                            body: ["name": name, "kind": "ios", "capabilities": ["image_finalize"], "limits": limits.dictionary])
            token = reply.token; deviceID = device.device.id; deviceToken = device.token
            SessionStore.save(try JSONEncoder().encode(SavedSession(server: server, token: token, deviceID: deviceID, deviceToken: deviceToken)))
            connected = true
            await refresh()
            startLoops()
        } catch { self.error = error.localizedDescription }
    }

    @discardableResult
    func refresh(reportError: Bool = true) async -> Bool {
        guard connected else { return false }
        let generation = contributionGate.generation
        let sessionToken = token
        let acknowledgmentRevision = acknowledgedJobs.revision
        let request = snapshotGate.begin(acknowledgmentRevision: acknowledgmentRevision)
        do {
            let state = try await api.json(Snapshot.self, "/api/state", token: token)
            guard !Task.isCancelled, generation == contributionGate.generation, sessionToken == token, connected else { return false }
            guard snapshotGate.accept(request, acknowledgmentRevision: acknowledgedJobs.revision) else { return true }
            snapshot = state
            acknowledgedJobs.reconcile(state.jobs, requestedAt: acknowledgmentRevision)
            if sharing, let device = state.devices.first(where: { $0.id == deviceID }), !device.enabled {
                stopLocalWork(); stage = "Session ended"
            }
            for event in state.events {
                if didLoadEvents && !seenEvents.contains(event.id) && event.shouldNotify(userID: state.user.id, deviceID: deviceID) {
                    await notify(event)
                }
                seenEvents.insert(event.id)
            }
            didLoadEvents = true
            return true
        } catch {
            guard connected, sessionToken == token else { return false }
            // An obsolete response is intentionally ignored, not a new status
            // failure that should replace a successful submission acknowledgment.
            guard snapshotGate.isCurrent(request, acknowledgmentRevision: acknowledgedJobs.revision) else { return true }
            if reportError && !Task.isCancelled { self.error = error.localizedDescription }
            return false
        }
    }

    func start() async {
        guard connected, foreground, !busy, !contributionTransition,
              let generation = contributionGate.beginStart() else { return }
        contributionTransition = true
        busy = true; error = nil
        defer {
            busy = false
            contributionGate.finishStart()
            contributionTransition = contributionGate.transitioning
        }
        let startAPI = api
        let startToken = token
        let startDeviceID = deviceID
        do {
            _ = try await startAPI.data("/api/devices/\(startDeviceID)", token: startToken, method: "PATCH",
                                   body: ["enabled": true, "limits": limits.dictionary])
            guard contributionGate.permits(generation, foreground: foreground), connected else {
                // A late Start might have reached the server after the earlier
                // Pause. Revoke it before allowing another explicit Start.
                if connected, token == startToken, deviceID == startDeviceID {
                    await pause()
                } else {
                    // Disconnect may have already cleared the current session.
                    _ = try? await startAPI.data("/api/devices/\(startDeviceID)", token: startToken,
                                                 method: "PATCH", body: ["enabled": false])
                }
                return
            }
            sharing = true; stage = "Available for image finishing"
            workerTask?.cancel()
            workerTask = Task { await workLoop(generation: generation) }
            await refresh()
        } catch { self.error = error.localizedDescription }
    }

    func pause() async {
        contributionGate.beginPause()
        contributionTransition = true
        defer {
            contributionGate.finishPause()
            contributionTransition = contributionGate.transitioning
        }
        stopLocalWork(); stage = "Paused"
        guard connected else { return }
        do {
            _ = try await api.data("/api/devices/\(deviceID)", token: token, method: "PATCH", body: ["enabled": false])
        } catch {
            self.error = "Stopped locally. Coordinator unavailable; its lease will expire. \(error.localizedDescription)"
        }
        await refresh()
    }

    func setForeground(_ value: Bool) {
        foreground = value
        if value {
            if connected { startLoops() }
        } else {
            stopLocalWork(); stage = "Paused in background"
            contributionTransition = true
            pollTask?.cancel(); heartbeatTask?.cancel()
            // Best effort server update. Lease expiry covers an interrupted request.
            Task { await pause() }
        }
    }

    private func stopLocalWork() {
        contributionGate.invalidate()
        sharing = false; workerTask?.cancel(); renderTask?.cancel(); workerTask = nil; renderTask = nil
        active = nil; progress = 0
    }

    private func startLoops() {
        pollTask?.cancel(); heartbeatTask?.cancel()
        pollTask = Task {
            while !Task.isCancelled && foreground {
                await refresh()
                do { try await Task.sleep(for: .seconds(2)) } catch { break }
            }
        }
        heartbeatTask = Task {
            while !Task.isCancelled && foreground {
                let generation = contributionGate.generation
                do {
                    var body: [String: Any] = ["telemetry": ["backend": "Swift/CoreGraphics · 1 CPU thread", "progress": progress, "stage": stage]]
                    let sentTask = active
                    if let task = sentTask, let lease = task.lease_id { body["task_id"] = task.id; body["lease_id"] = lease }
                    let reply = try await api.json(HeartbeatReply.self, "/api/devices/\(deviceID)/heartbeat", token: deviceToken, method: "POST", body: body)
                    try Task.checkCancellation()
                    if generation == contributionGate.generation && sharing &&
                        (!reply.device.enabled || (sentTask != nil && active?.lease_id == sentTask?.lease_id && !reply.lease_valid)) {
                        stopLocalWork(); stage = "Paused: contribution or lease ended"
                    }
                } catch {
                    if !Task.isCancelled && generation == contributionGate.generation {
                        // Fail closed when coordination is lost; never keep processing unseen.
                        stopLocalWork(); stage = "Paused: connection lost"; self.error = error.localizedDescription
                    }
                }
                do { try await Task.sleep(for: .seconds(3)) } catch { break }
            }
        }
    }

    private func workLoop(generation: Int) async {
        while sharing && contributionGate.permits(generation, foreground: foreground) && !Task.isCancelled {
            do {
                let claim = try await api.json(ClaimReply.self, "/api/devices/\(deviceID)/claim", token: deviceToken, method: "POST", body: [:])
                try Task.checkCancellation()
                guard contributionGate.permits(generation, foreground: foreground) else { return }
                if !claim.device.enabled { stopLocalWork(); stage = "Session ended"; return }
                if let task = claim.task { await process(task, maxPixels: claim.device.limits.max_pixels, generation: generation) }
                else { stage = "Available for image finishing" }
                try await Task.sleep(for: .seconds(1))
            } catch {
                if !Task.isCancelled && generation == contributionGate.generation { self.error = error.localizedDescription; stopLocalWork(); stage = "Paused after error" }
                return
            }
        }
    }

    private func process(_ task: GridTask, maxPixels: Int, generation: Int) async {
        guard let lease = task.lease_id else { return }
        active = task; progress = 0.05; stage = "Downloading image"
        let start = Date()
        do {
            guard task.kind == "image_finalize", let source = task.source_url else { throw ImageProcessor.Failure.invalidImage }
            let data = try await api.data(source, token: deviceToken)
            try Task.checkCancellation()
            guard contributionGate.permits(generation, foreground: foreground) else { throw CancellationError() }
            progress = 0.3; stage = "Applying export frame locally"
            _ = try await api.data("/api/tasks/\(task.id)/progress", token: deviceToken, method: "POST",
                                   body: ["lease_id": lease, "progress": progress, "stage": stage])
            try Task.checkCancellation()
            guard contributionGate.permits(generation, foreground: foreground) else { throw CancellationError() }
            let render = Task.detached(priority: .utility) { try ImageProcessor.finalize(data, maxPixels: maxPixels) }
            renderTask = render
            let result = try await withTaskCancellationHandler(operation: { try await render.value }, onCancel: { render.cancel() })
            try Task.checkCancellation()
            guard contributionGate.permits(generation, foreground: foreground) else { throw CancellationError() }
            progress = 0.85; stage = "Submitting finished image"
            _ = try await api.data("/api/tasks/\(task.id)/complete", token: deviceToken, method: "POST",
                                   body: ["lease_id": lease, "png_base64": result.base64EncodedString(),
                                          "metrics": ["backend": "Swift/CoreGraphics", "elapsed_seconds": Date().timeIntervalSince(start)]])
            try Task.checkCancellation()
            guard generation == contributionGate.generation else { return }
            notice = "Image finished on this phone. Accepted work earns \(task.price) sandbox credit(s)."
            if active?.lease_id == lease { active = nil; progress = 0; renderTask = nil }
            await refresh()
        } catch {
            if !Task.isCancelled && generation == contributionGate.generation {
                _ = try? await api.data("/api/tasks/\(task.id)/fail", token: deviceToken, method: "POST",
                                        body: ["lease_id": lease, "error": error.localizedDescription])
                if generation == contributionGate.generation { self.error = "Image finishing: \(error.localizedDescription)" }
            }
            if active?.lease_id == lease { active = nil; progress = 0; renderTask = nil }
        }
    }

    func submit(prompt: String, count: Int, budget: Int, useAgent: Bool) async {
        guard !busy else { return }
        busy = true; submitting = true; error = nil
        notice = "Submitting request…"
        let sessionToken = token
        do {
            var body: [String: Any] = ["prompt": prompt, "count": count, "width": 256, "height": 256,
                                      "steps": 12, "budget": budget, "use_agent": useAgent]
            // Reuse the request ID after an uncertain response for the same account and inputs.
            let signature = try JSONSerialization.data(withJSONObject: ["server": server, "account": token, "body": body], options: [.sortedKeys])
            if pendingSubmission?.signature != signature {
                pendingSubmission = (signature, UUID().uuidString)
            }
            body["request_id"] = pendingSubmission!.id
            let accepted = try await api.json(GridJob.self, "/api/jobs", token: token, method: "POST", body: body)
            guard connected, token == sessionToken else { busy = false; submitting = false; return }
            pendingSubmission = nil
            acknowledgedJobs.retain(accepted)
            notice = accepted.submissionAcknowledgement
            busy = false; submitting = false
        } catch {
            busy = false; submitting = false
            notice = nil
            if (error as? URLError)?.code == .timedOut {
                self.error = "The request acknowledgement timed out; the job may still be saved or running. Check your jobs before retrying. Retrying unchanged inputs in this app session reuses the same request ID."
            } else {
                self.error = error.localizedDescription
            }
            return
        }
        // This is separate from POST failure: a saved job must remain visible
        // and cancellable if fetching the next snapshot is unavailable.
        if !(await refresh(reportError: false)), connected, token == sessionToken, !Task.isCancelled {
            error = "Request saved, but its latest status could not be refreshed. Its job card remains available. Pull to refresh."
        }
    }

    func cancel(_ job: GridJob) async {
        let sessionToken = token
        do {
            let cancelled = try await api.json(GridJob.self, "/api/jobs/\(job.id)/cancel", token: sessionToken, method: "POST", body: [:])
            guard connected, token == sessionToken else { return }
            acknowledgedJobs.retain(cancelled)
            notice = cancelled.terminalSummary
            if !(await refresh(reportError: false)), connected, token == sessionToken, !Task.isCancelled {
                error = "Cancellation acknowledged, but the latest grid status could not be refreshed. The saved receipt remains below."
            }
        } catch {
            if connected, token == sessionToken, !Task.isCancelled { self.error = error.localizedDescription }
        }
    }

    func image(_ path: String) async throws -> Data { try await api.data(path, token: token) }

    func enableNotifications() async {
        do {
            let accepted = try await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])
            notificationStatus = accepted ? "Enabled" : "Disabled in Settings"
        } catch { self.error = error.localizedDescription }
    }

    private func notify(_ event: GridEvent) async {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        guard settings.authorizationStatus == .authorized else { return }
        let content = UNMutableNotificationContent()
        content.title = "PocketGrid"; content.body = event.message; content.sound = .default
        try? await UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: String(event.id), content: content, trigger: nil))
    }

    func disconnect() async {
        await pause()
        pollTask?.cancel(); heartbeatTask?.cancel()
        SessionStore.save(nil)
        connected = false; snapshot = nil; token = ""; deviceToken = ""; deviceID = ""
        acknowledgedJobs = AcknowledgedJobs()
        snapshotGate = SnapshotGate()
        seenEvents = []; didLoadEvents = false; error = nil; notice = nil
    }
}
