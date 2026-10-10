import Foundation

/// Uses the app's exact networking, decoding, and image-processing sources.
/// Requires a real generation worker connected to the coordinator.
@main
struct CoordinatorSmoke {
    static func main() async throws {
        let api = GridAPI(server: CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "http://127.0.0.1:8787")
        let session = try await api.json(SessionReply.self, "/api/sessions", token: nil, method: "POST",
                                         body: ["name": "Swift integration \(UUID().uuidString.prefix(6))",
                                                "join_code": ProcessInfo.processInfo.environment["POCKETGRID_JOIN_CODE"] ?? "pocketgrid-demo"])
        let device = try await api.json(DeviceReply.self, "/api/devices", token: session.token, method: "POST",
                                        body: ["name": "Native Swift image finalizer", "kind": "ios", "capabilities": ["image_finalize"], "limits": Limits().dictionary])
        _ = try await api.data("/api/devices/\(device.device.id)", token: session.token, method: "PATCH", body: ["enabled": true])
        do {
            let job = try await api.json(GridJob.self, "/api/jobs", token: session.token, method: "POST",
                                          body: ["prompt": "A paper boat on a sunny pond, colorful storybook illustration",
                                                 "count": 1, "width": 256, "height": 256, "steps": 12,
                                                 "budget": 10, "request_id": UUID().uuidString, "use_agent": false])
            print("Swift submitted real generation job \(job.id)")
            var accepted = 0
            var completed = false
            let deadline = Date().addingTimeInterval(240)
            while Date() < deadline {
                _ = try await api.json(HeartbeatReply.self, "/api/devices/\(device.device.id)/heartbeat", token: device.token,
                                       method: "POST", body: ["telemetry": ["backend": "Swift/CoreGraphics test"]])
                let claim = try await api.json(ClaimReply.self, "/api/devices/\(device.device.id)/claim", token: device.token,
                                                method: "POST", body: [:])
                if let task = claim.task, let lease = task.lease_id, let source = task.source_url {
                    let input = try await api.data(source, token: device.token)
                    let output = try ImageProcessor.finalize(input, maxPixels: 262144)
                    _ = try await api.data("/api/tasks/\(task.id)/progress", token: device.token, method: "POST",
                                           body: ["lease_id": lease, "progress": 0.8, "stage": "Native Swift framed real generated image"])
                    let body: [String: Any] = ["lease_id": lease, "png_base64": output.base64EncodedString(), "metrics": ["backend": "Swift/CoreGraphics"]]
                    let receipt = try await api.data("/api/tasks/\(task.id)/complete", token: device.token, method: "POST", body: body)
                    print("Native pixel output accepted: \(String(data: receipt, encoding: .utf8)!)")
                    let duplicate = try await api.data("/api/tasks/\(task.id)/complete", token: device.token, method: "POST", body: body)
                    print("Idempotent completion retry: \(String(data: duplicate, encoding: .utf8)!)")
                    accepted += 1
                }
                let state = try await api.json(Snapshot.self, "/api/state", token: session.token)
                if let finished = state.jobs.first(where: { $0.id == job.id }), let receipt = finished.receipt {
                    guard finished.status == "completed", receipt.total_charged == 8, receipt.refund == 2 else {
                        fatalError("Unexpected job receipt: \(finished.status), charged \(receipt.total_charged)")
                    }
                    print("Swift decoded completed job receipt: workers=\(receipt.contributor_total), fee=\(receipt.platform_fee), refund=\(receipt.refund)")
                    if accepted > 0 {
                        guard state.earned == accepted else { fatalError("Duplicate completion changed earned balance") }
                        print("PASS: native Swift API/image/ledger integration, accepted=\(accepted), earned=\(state.earned)")
                        completed = true
                        break
                    }
                }
                try await Task.sleep(for: .seconds(1))
            }
            _ = try await api.data("/api/devices/\(device.device.id)", token: session.token, method: "PATCH", body: ["enabled": false])
            let paused = try await api.json(ClaimReply.self, "/api/devices/\(device.device.id)/claim", token: device.token, method: "POST", body: [:])
            guard !paused.device.enabled, paused.task == nil else { fatalError("Paused worker claimed work") }
            guard accepted > 0 else { fatalError("No finalize task available for Swift worker before deadline") }
            guard completed else { fatalError("Submitted job did not complete before deadline") }
            print("PASS: paused native worker receives no tasks")
        } catch {
            _ = try? await api.data("/api/devices/\(device.device.id)", token: session.token, method: "PATCH", body: ["enabled": false])
            throw error
        }
    }
}
