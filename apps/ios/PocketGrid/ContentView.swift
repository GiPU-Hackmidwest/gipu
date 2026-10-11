import SwiftUI

private enum GridStyle {
    static let orange = Color(red: 1, green: 0.412, blue: 0.043)
    static let actionInk = Color(red: 0.153, green: 0.078, blue: 0.020)
    static let background = Color(uiColor: .systemGroupedBackground)
    static let panel = Color(uiColor: .secondarySystemGroupedBackground)
}

private struct GridPrimaryButton: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.font(.headline).foregroundStyle(GridStyle.actionInk)
            .frame(maxWidth: .infinity, minHeight: 48)
            .padding(.horizontal, 16).padding(.vertical, 5)
            .background(GridStyle.orange.opacity(configuration.isPressed ? 0.75 : 1), in: Capsule())
            .opacity(isEnabled ? 1 : 0.45)
    }
}

private struct GridPanel: ViewModifier {
    func body(content: Content) -> some View {
        content.padding(24).frame(maxWidth: .infinity, alignment: .leading)
            .background(GridStyle.panel, in: RoundedRectangle(cornerRadius: 34, style: .continuous))
    }
}

private extension View {
    func gridPanel() -> some View { modifier(GridPanel()) }
}

private struct DeviceTile: View {
    let symbol: String
    let name: String
    let status: String
    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: symbol)
                .font(.system(size: 48, weight: .light))
                .foregroundStyle(.primary)
                .frame(maxWidth: .infinity).frame(height: 116)
                .background(GridStyle.panel, in: RoundedRectangle(cornerRadius: 32, style: .continuous))
                .shadow(color: .black.opacity(0.045), radius: 14, x: 0, y: 8)
                .accessibilityHidden(true)
            VStack(spacing: 4) {
                Text(name).font(.subheadline.weight(.medium))
                Text(status).font(.caption).foregroundStyle(.secondary)
            }
        }.accessibilityElement(children: .ignore)
            .accessibilityLabel("\(symbol == "laptopcomputer" ? "Laptop" : "Finishing device"), \(status)")
    }
}

private struct HandoffDevice: View {
    let symbol: String
    let name: String
    let status: String
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: symbol)
                .font(.system(size: symbol == "laptopcomputer" ? 62 : 54, weight: .ultraLight))
                .frame(width: 104, height: 104)
                .background(GridStyle.panel, in: Circle())
                .shadow(color: .black.opacity(0.06), radius: 14, x: 0, y: 9)
            HStack(spacing: 5) {
                Text(name).fontWeight(.medium)
                Text(status).foregroundStyle(.secondary)
            }.font(.caption)
        }.accessibilityElement(children: .ignore)
            .accessibilityLabel("\(name), \(status)")
    }
}

/// Counts only capacity observed in the latest snapshot; never implies assignment.
private struct DeviceHandoff: View {
    @EnvironmentObject private var grid: GridModel
    @Environment(\.dynamicTypeSize) private var typeSize
    var body: some View {
        Group {
            if typeSize.isAccessibilitySize {
                VStack(spacing: 20) {
                    DeviceTile(symbol: "laptopcomputer", name: "Create", status: availability("image_generate"))
                    Image(systemName: "arrow.down").foregroundStyle(.secondary).accessibilityHidden(true)
                    DeviceTile(symbol: "iphone", name: "Finish", status: availability("image_finalize"))
                }
            } else {
                GeometryReader { geometry in
                    let width = geometry.size.width
                    ZStack {
                        Path { path in
                            path.move(to: CGPoint(x: width * 0.29, y: 76))
                            path.addCurve(to: CGPoint(x: width * 0.72, y: 188),
                                          control1: CGPoint(x: width * 1.05, y: 70),
                                          control2: CGPoint(x: width * 0.04, y: 196))
                        }.stroke(.primary.opacity(0.25), style: StrokeStyle(lineWidth: 2, lineCap: .round))
                            .accessibilityHidden(true)
                        HandoffDevice(symbol: "laptopcomputer", name: "Laptop", status: availability("image_generate"))
                            .position(x: width * 0.28, y: 86)
                        HandoffDevice(symbol: "iphone", name: "Finisher", status: availability("image_finalize"))
                            .position(x: width * 0.73, y: 196)
                    }
                }.frame(height: 272)
                    .background(.primary.opacity(0.025), in: RoundedRectangle(cornerRadius: 38, style: .continuous))
            }
        }.padding(.vertical, 8)
    }

    private func availability(_ kind: String) -> String {
        guard let snapshot = grid.snapshot, let now = snapshot.server_time else { return "Checking…" }
        let compatible = snapshot.devices.filter {
            $0.online && $0.enabled && ($0.session_expires_at ?? 0) > now &&
            $0.capabilities?.contains(kind) == true && $0.limits.max_pixels >= 65536
        }
        let ready = compatible.filter { $0.active_task_id == nil }.count
        if ready > 0 { return "\(ready) ready" }
        if snapshot.devices.contains(where: { $0.online && $0.enabled && ($0.capabilities == nil || $0.session_expires_at == nil) }) {
            return "Checking…"
        }
        return compatible.isEmpty ? "None ready" : "Busy"
    }
}

struct ContentView: View {
    @EnvironmentObject private var grid: GridModel
    var body: some View {
        Group {
            if grid.connected {
                TabView {
                    CreateView().tabItem { Label("Create", systemImage: "photo.fill") }
                    ContributeView().tabItem { Label("Contribute", systemImage: "cpu.fill") }
                    ActivityView().tabItem { Label("Activity", systemImage: "bell.fill") }
                }
            } else { JoinView() }
        }
        .tint(Color.primary)
        .alert("PocketGrid", isPresented: Binding(get: { grid.error != nil }, set: { if !$0 { grid.error = nil } })) {
            Button("OK") { grid.error = nil }
        } message: { Text(grid.error ?? "") }
    }
}

private struct JoinView: View {
    @EnvironmentObject private var grid: GridModel
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 30) {
                    HStack(spacing: 14) {
                        DeviceTile(symbol: "laptopcomputer", name: "Create", status: "On a laptop")
                        DeviceTile(symbol: "iphone", name: "Finish", status: "With a little help")
                    }.padding(.vertical, 24)
                    VStack(alignment: .leading, spacing: 22) {
                        Text("Join the grid").font(.title2.weight(.medium))
                        TextField("Your name", text: $grid.name).textContentType(.name)
                        Divider()
                        SecureField("Join code", text: $grid.joinCode).textInputAutocapitalization(.never)
                        DisclosureGroup("Grid address") {
                            TextField("https://…", text: $grid.server).textContentType(.URL).keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled().padding(.top, 10)
                        }.font(.subheadline)
                        Button { Task { await grid.join() } } label: {
                            HStack { Text("Join grid"); if grid.busy { ProgressView() } }
                        }.buttonStyle(GridPrimaryButton()).disabled(grid.busy || grid.name.trimmingCharacters(in: .whitespaces).isEmpty)
                        Text("Sharing starts only when you choose.").font(.caption).foregroundStyle(.secondary)
                    }.gridPanel()
                    DisclosureGroup("About this grid") {
                        Text("Grid members can see prompts and images. Use public demo material. Credits have no cash value.").font(.footnote).padding(.top, 8)
                    }.font(.subheadline).padding(.horizontal, 12)
                }.padding(24).frame(maxWidth: 580)
                    .frame(maxWidth: .infinity)
            }.background(GridStyle.background).navigationTitle("PocketGrid").navigationBarTitleDisplayMode(.inline)
        }
    }
}

private struct BalanceView: View {
    @EnvironmentObject private var grid: GridModel
    @Environment(\.dynamicTypeSize) private var typeSize
    var body: some View {
        let layout = typeSize.isAccessibilitySize ? AnyLayout(VStackLayout(alignment: .leading, spacing: 16)) : AnyLayout(HStackLayout(alignment: .top, spacing: 20))
        layout {
            metric("Available", grid.snapshot?.balance ?? 0)
            metric("Reserved", grid.snapshot?.reserved ?? 0)
            metric("Earned", grid.snapshot?.earned ?? 0)
        }.accessibilityElement(children: .combine)
    }
    private func metric(_ label: String, _ value: Int) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(grid.snapshot == nil ? "—" : "\(value)").font(.title.monospacedDigit().weight(.medium))
            Text(label).font(.caption).foregroundStyle(.secondary)
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct CreateView: View {
    @EnvironmentObject private var grid: GridModel
    @State private var prompt = "A cat riding a tiny bicycle, playful illustration"
    @State private var count = 1
    @State private var budget = 10
    @State private var useAgent = false
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    DeviceHandoff()
                    VStack(alignment: .leading, spacing: 20) {
                        TextField("What do you imagine?", text: $prompt, axis: .vertical)
                            .font(.title3).lineLimit(3...6).accessibilityLabel("Image prompt")
                        HStack {
                            Text("\(count * 7 + 1) credits estimated").font(.caption).foregroundStyle(.secondary)
                            Spacer()
                            Text("\(grid.snapshot?.balance ?? 0) available").font(.caption).foregroundStyle(.secondary)
                        }
                        DisclosureGroup("Options") {
                            VStack(spacing: 18) {
                                Stepper("Images: \(count)", value: $count, in: 1...4)
                                    .onChange(of: count) { _, value in budget = max(budget, value * 7 + 1) }
                                Stepper("Budget: \(budget)", value: $budget, in: (count * 7 + 1)...100)
                                Toggle("Smart device selection", isOn: $useAgent).disabled(grid.snapshot?.agent.available != true)
                                Text(grid.snapshot?.agent.available == true ? "A planner chooses suitable devices." : "Smart selection is unavailable. Devices can still accept requests.").font(.caption).foregroundStyle(.secondary)
                            }.padding(.top, 18)
                        }.font(.subheadline)
                        Button { Task { await grid.submit(prompt: prompt, count: count, budget: budget, useAgent: useAgent) } } label: {
                            HStack { Text(grid.submitting ? "Creating…" : "Create image"); if grid.submitting { ProgressView() } }
                        }.buttonStyle(GridPrimaryButton()).disabled(grid.busy || grid.submitting || grid.snapshot == nil || budget > (grid.snapshot?.balance ?? 0) || prompt.trimmingCharacters(in: .whitespaces).isEmpty)
                        Text("Reserves \(budget) credits. Unused credits return.").font(.caption).foregroundStyle(.secondary)
                    }.gridPanel()
                    if let notice = grid.notice { Text(notice).font(.footnote).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading) }
                    ForEach(grid.ownJobs) { job in JobCard(job: job) }
                }.padding(24).frame(maxWidth: 580).frame(maxWidth: .infinity)
            }.background(GridStyle.background).navigationTitle("Create").navigationBarTitleDisplayMode(.inline)
                .refreshable { await grid.refresh() }
        }
    }
}

private struct JobCard: View {
    @EnvironmentObject private var grid: GridModel
    let job: GridJob
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(job.prompt).font(.headline)
            Text(job.statusLabel).font(.caption.weight(.medium)).foregroundStyle(.secondary)
            JobProgressView(job: job)
            ForEach(job.displayImages) { item in ProtectedImage(path: item.url, stage: item.stage, variant: item.variant) }
            if !job.tasks.isEmpty {
                DisclosureGroup("Devices") {
                    ForEach(job.tasks) { task in
                        VStack(alignment: .leading, spacing: 4) {
                            Text("\(task.kind == "image_generate" ? "Create" : "Finish") · image \(task.variant + 1)")
                            Text("\(task.device_id.flatMap { id in grid.snapshot?.devices.first { $0.id == id }?.name } ?? "Awaiting device") · \(task.status)").font(.caption).foregroundStyle(.secondary)
                        }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 8)
                    }
                }.font(.subheadline)
            }
            if let receipt = job.receipt {
                DisclosureGroup("Receipt · \(receipt.total_charged) credits") {
                    VStack(spacing: 10) {
                        LabeledContent("Reserved", value: "\(receipt.budget)")
                        LabeledContent("Contributors", value: "\(receipt.contributor_total)")
                        LabeledContent("Service", value: "\(receipt.platform_fee)")
                        LabeledContent("Charged", value: "\(receipt.total_charged)").fontWeight(.medium)
                        LabeledContent("Returned", value: "\(receipt.refund)")
                        Text("Sandbox credits · no cash value").font(.caption).foregroundStyle(.secondary)
                    }.padding(.top, 12)
                }.font(.subheadline)
            } else { Text("\(job.reservedCredits) credits reserved").font(.caption).foregroundStyle(.secondary) }
            if job.isActive {
                Button("Cancel request", role: .destructive) { Task { await grid.cancel(job) } }.frame(minHeight: 44)
            }
        }.gridPanel()
    }
}

private struct JobProgressView: View {
    @EnvironmentObject private var grid: GridModel
    let job: GridJob
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if job.isPlanning { ProgressView(job.planningTitle) }
            else {
                if let summary = job.terminalSummary { Text(summary).font(.subheadline).foregroundStyle(.secondary) }
                if !job.tasks.isEmpty && job.isActive {
                    let generated = job.completedCount("image_generate")
                    let finished = job.completedCount("image_finalize")
                    ProgressView(value: Double(generated + finished), total: Double(max(1, job.imageCount * 2)))
                        .tint(GridStyle.orange)
                        .accessibilityLabel("Image processing steps")
                        .accessibilityValue("\(generated) of \(job.imageCount) generated, \(finished) of \(job.imageCount) finished")
                    stage("Create", kind: "image_generate", completed: generated)
                    stage("Finish", kind: "image_finalize", completed: finished)
                }
            }
            if !grid.sharing && job.canStartFinishing(on: grid.ownDevice, limits: grid.limits) {
                Button("Help finish on this phone") { Task { await grid.start() } }
                    .buttonStyle(GridPrimaryButton()).disabled(grid.busy || grid.contributionTransition)
                Text("Share for \(grid.limits.session_minutes) minutes. Keep the app open. Pause in Contribute.").font(.caption).foregroundStyle(.secondary)
            }
        }
    }
    private func stage(_ title: String, kind: String, completed: Int) -> some View {
        let state = job.stageState(kind, devices: grid.snapshot?.devices ?? [], serverTime: grid.snapshot?.server_time)
        return VStack(alignment: .leading, spacing: 3) {
            Text("\(title) · \(completed)/\(job.imageCount)").font(.subheadline.weight(.medium))
            Text(stageMessage(state, kind: kind)).font(.caption).foregroundStyle(.secondary)
        }.accessibilityElement(children: .combine)
    }
    private func stageMessage(_ state: JobStageState, kind: String) -> String {
        let generation = kind == "image_generate"
        switch state {
        case .planning: return "Choosing devices…"
        case .running: return generation ? "Creating on a laptop…" : "Finishing on a device…"
        case .complete: return "Done"
        case .waitingForGeneration: return "Up next"
        case .ready: return generation ? "Waiting for a laptop" : "Waiting for a device"
        case .busy: return "Devices are busy. You’re in line."
        case .unavailable: return generation ? "Start sharing on a compatible laptop." : "Start sharing on a compatible device."
        case .unknown: return "Checking devices…"
        case .stopped: return "Stopped"
        }
    }
}

private struct ProtectedImage: View {
    @EnvironmentObject private var grid: GridModel
    let path: String
    let stage: String
    let variant: Int
    @State private var image: UIImage?
    @State private var failed = false
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let image {
                Image(uiImage: image).resizable().scaledToFit().frame(maxHeight: 340)
                    .clipShape(RoundedRectangle(cornerRadius: 24)).accessibilityLabel("Image \(variant + 1), \(stageLabel)")
                ShareLink(item: Image(uiImage: image), preview: SharePreview("PocketGrid · image \(variant + 1)", image: Image(uiImage: image))) {
                    Label(stage == "image_finalize" ? "Share image" : "Share preview", systemImage: "square.and.arrow.up")
                }.buttonStyle(.bordered).controlSize(.large)
            } else if failed { Label("Image unavailable", systemImage: "photo.badge.exclamationmark") }
            else { ProgressView() }
            Text("Image \(variant + 1) · \(stageLabel)").font(.caption).foregroundStyle(.secondary)
        }.task(id: path) {
            do { image = UIImage(data: try await grid.image(path)); failed = image == nil }
            catch { failed = true }
        }
    }
    private var stageLabel: String { stage == "image_finalize" ? "Ready" : "Unfinished preview" }
}

private struct SessionDial: View {
    @EnvironmentObject private var grid: GridModel
    var body: some View {
        TimelineView(.periodic(from: .now, by: 1)) { context in
            let remaining = grid.sharing ? max(0, (grid.ownDevice?.session_expires_at ?? context.date.timeIntervalSince1970) - context.date.timeIntervalSince1970) : 0
            let duration = Double(max(1, grid.ownDevice?.limits.session_minutes ?? grid.limits.session_minutes) * 60)
            ZStack {
                Circle().stroke(GridStyle.panel, lineWidth: 28)
                    .shadow(color: .black.opacity(0.04), radius: 12, x: 0, y: 8)
                if grid.sharing, grid.ownDevice?.session_expires_at != nil {
                    Circle().trim(from: 0, to: min(1, remaining / duration))
                        .stroke(GridStyle.orange, style: StrokeStyle(lineWidth: 28, lineCap: .round)).rotationEffect(.degrees(-90))
                }
                VStack(spacing: 14) {
                    Image(systemName: grid.sharing ? "iphone.radiowaves.left.and.right" : "iphone")
                        .font(.system(size: 42, weight: .ultraLight)).accessibilityHidden(true)
                    Text(grid.sharing ? (grid.ownDevice?.session_expires_at == nil ? "Sharing" : timer(remaining)) : "Paused")
                        .font(.largeTitle.weight(.light).monospacedDigit()).minimumScaleFactor(0.6).lineLimit(1)
                    if grid.sharing, grid.ownDevice?.session_expires_at != nil {
                        Text("remaining").font(.caption).foregroundStyle(.secondary)
                    }
                }.padding(30)
            }.aspectRatio(1, contentMode: .fit).frame(maxWidth: 250).padding(18)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(grid.sharing ? "Sharing session" : "Sharing paused")
                .accessibilityValue(grid.sharing ? (grid.ownDevice?.session_expires_at == nil ? "Checking time remaining" : "\(Int(remaining) / 60) minutes, \(Int(remaining) % 60) seconds remaining") : "")
        }
    }
    private func timer(_ seconds: Double) -> String { String(format: "%02d:%02d", Int(seconds) / 60, Int(seconds) % 60) }
}

private struct ContributeView: View {
    @EnvironmentObject private var grid: GridModel
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    VStack(spacing: 8) {
                        Text(grid.ownDevice?.name ?? "This phone").font(.title3.weight(.medium))
                        Text(grid.sharing ? "Sharing while open" : "Connected · sharing paused").font(.caption).foregroundStyle(.secondary)
                    }.padding(.top, 12)
                    SessionDial()
                    VStack(alignment: .leading, spacing: 20) {
                        HStack {
                            Label("\(grid.ownDevice?.earned ?? 0) earned", systemImage: "circle.grid.2x2")
                            Spacer()
                            Text("\(grid.limits.session_minutes) min").foregroundStyle(.secondary)
                        }.font(.subheadline)
                        if let task = grid.active {
                            Text("Finishing image \(task.variant + 1)").font(.subheadline)
                            ProgressView(value: grid.progress).tint(GridStyle.orange)
                        } else if grid.sharing {
                            Text("Ready to help").font(.subheadline).foregroundStyle(.secondary)
                        }
                        if grid.sharing {
                            Button { Task { await grid.pause() } } label: { Label("Pause sharing", systemImage: "pause.fill") }.buttonStyle(GridPrimaryButton())
                        } else {
                            Button { Task { await grid.start() } } label: { Label(grid.contributionTransition ? "Connecting…" : "Start sharing", systemImage: "play.fill") }.buttonStyle(GridPrimaryButton()).disabled(grid.busy || grid.contributionTransition)
                        }
                        Text("Leaving the app pauses sharing.").font(.caption).foregroundStyle(.secondary)
                        DisclosureGroup("Limits") {
                            VStack(spacing: 18) {
                                Picker("Maximum image", selection: $grid.limits.max_pixels) {
                                    Text("256 × 256").tag(65536)
                                    Text("384 × 384").tag(147456)
                                    Text("512 × 512").tag(262144)
                                }
                                Stepper("Session: \(grid.limits.session_minutes) min", value: $grid.limits.session_minutes, in: 5...120, step: 5)
                                Text(grid.sharing ? "Pause to change limits." : "One image at a time. Limits control image size and time, not memory or GPU usage.").font(.caption).foregroundStyle(.secondary)
                            }.padding(.top, 14).disabled(grid.sharing || grid.contributionTransition)
                        }.font(.subheadline)
                    }.gridPanel()
                    DisclosureGroup("How sharing works") {
                        Text("Your phone adds a frame to images made by laptops. Earn sandbox credits when finished work is accepted.").font(.footnote).padding(.top, 8)
                    }.font(.subheadline).padding(.horizontal, 12)
                }.padding(24).frame(maxWidth: 580).frame(maxWidth: .infinity)
            }.background(GridStyle.background).navigationTitle("Contribute").navigationBarTitleDisplayMode(.inline)
        }
    }
}

private struct ActivityView: View {
    @EnvironmentObject private var grid: GridModel
    var body: some View {
        NavigationStack {
            List {
                Section {
                    BalanceView().padding(.vertical, 12)
                } footer: { Text("Sandbox credits · no cash value") }
                Section {
                    Text(grid.snapshot?.user.name ?? "Connecting")
                    Button { Task { await grid.enableNotifications() } } label: { LabeledContent("Notifications", value: grid.notificationStatus) }
                    DisclosureGroup("Grid details") {
                        Text(URL(string: grid.server)?.host ?? grid.server).font(.caption)
                        Text("Alerts arrive while the app receives updates.").font(.caption).foregroundStyle(.secondary)
                    }
                }
                Section("Devices") {
                    ForEach(grid.snapshot?.devices ?? []) { device in
                        HStack(spacing: 14) {
                            Image(systemName: device.capabilities?.contains("image_generate") == true ? "laptopcomputer" : "iphone").frame(width: 32).accessibilityHidden(true)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(device.name)
                                Text(sharingStatus(device)).font(.caption).foregroundStyle(.secondary)
                            }
                        }.padding(.vertical, 6)
                    }
                }
                Section("Activity") {
                    if grid.snapshot?.events.isEmpty == true { Text("Nothing yet").foregroundStyle(.secondary) }
                    ForEach(grid.snapshot?.events ?? []) { event in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(event.message)
                            Text(Date(timeIntervalSince1970: event.created_at), style: .time).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
                Section { Button("Disconnect this phone", role: .destructive) { Task { await grid.disconnect() } } }
            }.navigationTitle("Activity").navigationBarTitleDisplayMode(.inline)
                .scrollContentBackground(.hidden).background(GridStyle.background).refreshable { await grid.refresh() }
        }
    }
    private func sharingStatus(_ device: Device) -> String {
        guard device.online else { return "Offline" }
        guard device.enabled else { return "Connected · paused" }
        guard let now = grid.snapshot?.server_time, let expiry = device.session_expires_at else { return "Checking session…" }
        return expiry > now ? (device.active_task_id == nil ? "Sharing · ready" : "Sharing · working") : "Connected · session ended"
    }
}
