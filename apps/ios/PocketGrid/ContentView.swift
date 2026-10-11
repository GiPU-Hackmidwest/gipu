import SwiftUI

private enum GridStyle {
    static let orange = Color(red: 195.0 / 255, green: 68.0 / 255, blue: 0)
    static let actionInk = Color.white
    static let background = adaptive(0xF4F6F8, dark: 0x1C1E21)
    static let panel = adaptive(0xF5F6F8, dark: 0x282C31)
    static let inset = adaptive(0xE5E7EB, dark: 0x171A1E)
    static let ink = adaptive(0x1C1E21, dark: 0xF1F3F5)
    static let muted = adaptive(0x606770, dark: 0xABB3BD)
    static let highlight = adaptive(0xFFFFFF, dark: 0x454B54)
    static let shade = adaptive(0xB6BDC8, dark: 0x080A0D)

    private static func adaptive(_ light: UInt32, dark: UInt32) -> Color {
        Color(uiColor: UIColor { traits in
            let hex = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(red: CGFloat((hex >> 16) & 255) / 255,
                           green: CGFloat((hex >> 8) & 255) / 255,
                           blue: CGFloat(hex & 255) / 255, alpha: 1)
        })
    }
}

/// Opaque, softly lit material shared by panels, platforms, and recessed wells.
private struct ClaySurface<S: InsettableShape>: View {
    @Environment(\.colorSchemeContrast) private var contrast
    let shape: S
    var recessed = false
    var color = GridStyle.panel
    var compact = false

    var body: some View {
        shape.fill(color
            .shadow(.inner(color: (recessed ? GridStyle.shade : GridStyle.highlight).opacity(recessed ? 0.55 : 0.9),
                           radius: recessed ? 5 : 2, x: recessed ? 3 : -1, y: recessed ? 3 : -1))
            .shadow(.inner(color: (recessed ? GridStyle.highlight : GridStyle.shade).opacity(recessed ? 0.75 : 0.12),
                           radius: recessed ? 4 : 3, x: recessed ? -3 : 1, y: recessed ? -3 : 2)))
            .shadow(color: recessed ? .clear : GridStyle.highlight.opacity(0.8), radius: compact ? 5 : 12, x: compact ? -2 : -6, y: compact ? -2 : -6)
            .shadow(color: recessed ? .clear : GridStyle.shade.opacity(0.4), radius: compact ? 6 : 14, x: compact ? 3 : 7, y: compact ? 3 : 8)
            .overlay(shape.strokeBorder(contrast == .increased ? GridStyle.ink.opacity(0.45) : .clear, lineWidth: 1))
    }
}

private struct GridPrimaryButton: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.colorSchemeContrast) private var contrast
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.font(.headline).foregroundStyle(GridStyle.actionInk).tint(GridStyle.actionInk)
            .frame(maxWidth: .infinity, minHeight: 48)
            .padding(.horizontal, 16).padding(.vertical, 5)
            .background {
                ClaySurface(shape: Capsule(), recessed: configuration.isPressed,
                            color: GridStyle.orange, compact: true)
                    .overlay(Capsule().fill(.black.opacity(configuration.isPressed ? 0.08 : 0)))
            }
            .scaleEffect(configuration.isPressed && !reduceMotion ? 0.985 : 1)
            .animation(reduceMotion ? nil : .easeOut(duration: 0.12), value: configuration.isPressed)
            .overlay(Capsule().strokeBorder(contrast == .increased ? GridStyle.actionInk.opacity(0.7) : .clear, lineWidth: 1))
            .opacity(isEnabled ? 1 : 0.45)
    }
}

private struct GridPanel: ViewModifier {
    func body(content: Content) -> some View {
        content.padding(24).frame(maxWidth: .infinity, alignment: .leading)
            .background { ClaySurface(shape: RoundedRectangle(cornerRadius: 34, style: .continuous)) }
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
                .foregroundStyle(GridStyle.ink)
                .frame(maxWidth: .infinity).frame(height: 116)
                .background { ClaySurface(shape: RoundedRectangle(cornerRadius: 32, style: .continuous)) }
                .accessibilityHidden(true)
            VStack(spacing: 4) {
                Text(name).font(.subheadline.weight(.medium))
                Text(status).font(.caption).foregroundStyle(GridStyle.muted)
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
                .background { ClaySurface(shape: Circle(), recessed: true, color: GridStyle.inset).padding(5) }
                .background { ClaySurface(shape: Circle()) }
            HStack(spacing: 5) {
                Text(name).fontWeight(.medium)
                Text(status).foregroundStyle(GridStyle.muted)
            }.font(.caption).padding(.horizontal, 10).padding(.vertical, 7)
                .background { ClaySurface(shape: Capsule(), compact: true) }
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
                    Image(systemName: "arrow.down").foregroundStyle(GridStyle.muted).accessibilityHidden(true)
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
                        }.stroke(GridStyle.muted.opacity(0.6), style: StrokeStyle(lineWidth: 2, lineCap: .round))
                            .accessibilityHidden(true)
                        HandoffDevice(symbol: "laptopcomputer", name: "Laptop", status: availability("image_generate"))
                            .position(x: width * 0.28, y: 86)
                        HandoffDevice(symbol: "iphone", name: "Finisher", status: availability("image_finalize"))
                            .position(x: width * 0.73, y: 196)
                    }
                }.frame(height: 272)
                    .background { ClaySurface(shape: RoundedRectangle(cornerRadius: 38, style: .continuous), recessed: true, color: GridStyle.background) }
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
        .foregroundStyle(GridStyle.ink)
        .tint(GridStyle.ink)
        .alert("GiPU", isPresented: Binding(get: { grid.error != nil }, set: { if !$0 { grid.error = nil } })) {
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
                        Text("Sharing starts only when you choose.").font(.caption).foregroundStyle(GridStyle.muted)
                    }.gridPanel()
                }.padding(24).frame(maxWidth: 580)
                    .frame(maxWidth: .infinity)
            }.background(GridStyle.background).navigationTitle("GiPU").navigationBarTitleDisplayMode(.inline)
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
            Text(label).font(.caption).foregroundStyle(GridStyle.muted)
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct CreateView: View {
    @EnvironmentObject private var grid: GridModel
    @State private var prompt = "A cat riding a tiny bicycle, playful illustration"
    @State private var count = 1
    @State private var budget = 10
    @AppStorage("gipu.developerOptionsEnabled") private var developerOptionsEnabled = false
    @AppStorage("gipu.usePlanner") private var useAgent = false
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    DeviceHandoff()
                    VStack(alignment: .leading, spacing: 20) {
                        TextField("What do you imagine?", text: $prompt, axis: .vertical)
                            .font(.title3).lineLimit(3...6).accessibilityLabel("Image prompt")
                        HStack {
                            Text("\(count * 7 + 1) credits estimated").font(.caption).foregroundStyle(GridStyle.muted)
                            Spacer()
                            Text("\(grid.snapshot?.balance ?? 0) available").font(.caption).foregroundStyle(GridStyle.muted)
                        }
                        DisclosureGroup("Options") {
                            VStack(spacing: 18) {
                                Stepper("Images: \(count)", value: $count, in: 1...4)
                                    .onChange(of: count) { _, value in budget = max(budget, value * 7 + 1) }
                                Stepper("Budget: \(budget)", value: $budget, in: (count * 7 + 1)...100)
                            }.padding(.top, 18)
                        }.font(.subheadline)
                        Button { Task { await grid.submit(prompt: prompt, count: count, budget: budget, useAgent: developerOptionsEnabled && useAgent) } } label: {
                            HStack { Text(grid.submitting ? "Creating…" : "Create image"); if grid.submitting { ProgressView() } }
                        }.buttonStyle(GridPrimaryButton()).disabled(grid.busy || grid.submitting || grid.snapshot == nil || budget > (grid.snapshot?.balance ?? 0) || prompt.trimmingCharacters(in: .whitespaces).isEmpty)
                        Text("Reserves \(budget) credits. Unused credits return.").font(.caption).foregroundStyle(GridStyle.muted)
                    }.gridPanel()
                    if let notice = grid.notice { Text(notice).font(.footnote).foregroundStyle(GridStyle.muted).frame(maxWidth: .infinity, alignment: .leading) }
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
            Text(job.statusLabel).font(.caption.weight(.medium)).foregroundStyle(GridStyle.muted)
            JobProgressView(job: job)
            ForEach(job.displayImages) { item in ProtectedImage(path: item.url, stage: item.stage, variant: item.variant) }
            if let receipt = job.receipt {
                DisclosureGroup("Receipt · \(receipt.total_charged) credits") {
                    VStack(spacing: 10) {
                        LabeledContent("Reserved", value: "\(receipt.budget)")
                        LabeledContent("Contributors", value: "\(receipt.contributor_total)")
                        LabeledContent("Service", value: "\(receipt.platform_fee)")
                        LabeledContent("Charged", value: "\(receipt.total_charged)").fontWeight(.medium)
                        LabeledContent("Returned", value: "\(receipt.refund)")
                        Text("Sandbox credits · no cash value").font(.caption).foregroundStyle(GridStyle.muted)
                    }.padding(.top, 12)
                }.font(.subheadline)
            } else { Text("\(job.reservedCredits) credits reserved").font(.caption).foregroundStyle(GridStyle.muted) }
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
                if let summary = job.terminalSummary { Text(summary).font(.subheadline).foregroundStyle(GridStyle.muted) }
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
                Text("Share for \(grid.limits.session_minutes) minutes. Keep the app open. Pause in Contribute.").font(.caption).foregroundStyle(GridStyle.muted)
            }
        }
    }
    private func stage(_ title: String, kind: String, completed: Int) -> some View {
        let state = job.stageState(kind, devices: grid.snapshot?.devices ?? [], serverTime: grid.snapshot?.server_time)
        return VStack(alignment: .leading, spacing: 3) {
            Text("\(title) · \(completed)/\(job.imageCount)").font(.subheadline.weight(.medium))
            Text(stageMessage(state, kind: kind)).font(.caption).foregroundStyle(GridStyle.muted)
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
                ShareLink(item: Image(uiImage: image), preview: SharePreview("GiPU · image \(variant + 1)", image: Image(uiImage: image))) {
                    Label(stage == "image_finalize" ? "Share image" : "Share preview", systemImage: "square.and.arrow.up")
                }.buttonStyle(.bordered).controlSize(.large)
            } else if failed { Label("Image unavailable", systemImage: "photo.badge.exclamationmark") }
            else { ProgressView() }
            Text("Image \(variant + 1) · \(stageLabel)").font(.caption).foregroundStyle(GridStyle.muted)
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
                    .shadow(color: GridStyle.highlight.opacity(0.9), radius: 8, x: -5, y: -5)
                    .shadow(color: GridStyle.shade.opacity(0.5), radius: 10, x: 5, y: 7)
                ClaySurface(shape: Circle(), recessed: true, color: GridStyle.inset).padding(22)
                if grid.sharing, grid.ownDevice?.session_expires_at != nil {
                    Circle().trim(from: 0, to: min(1, remaining / duration))
                        .stroke(GridStyle.orange, style: StrokeStyle(lineWidth: 28, lineCap: .round))
                        .shadow(color: GridStyle.orange.opacity(0.2), radius: 4, x: 2, y: 3)
                        .rotationEffect(.degrees(-90))
                }
                VStack(spacing: 14) {
                    Image(systemName: grid.sharing ? "iphone.radiowaves.left.and.right" : "iphone")
                        .font(.system(size: 42, weight: .ultraLight)).accessibilityHidden(true)
                    Text(grid.sharing ? (grid.ownDevice?.session_expires_at == nil ? "Sharing" : timer(remaining)) : "Paused")
                        .font(.largeTitle.weight(.light).monospacedDigit()).minimumScaleFactor(0.6).lineLimit(1)
                    if grid.sharing, grid.ownDevice?.session_expires_at != nil {
                        Text("remaining").font(.caption).foregroundStyle(GridStyle.muted)
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
                        Text(grid.sharing ? "Sharing while open" : "Connected · sharing paused").font(.caption).foregroundStyle(GridStyle.muted)
                    }.padding(.top, 12)
                    SessionDial()
                    VStack(alignment: .leading, spacing: 20) {
                        HStack {
                            Label("\(grid.ownDevice?.earned ?? 0) earned", systemImage: "circle.grid.2x2")
                            Spacer()
                            Text("\(grid.limits.session_minutes) min").foregroundStyle(GridStyle.muted)
                        }.font(.subheadline)
                        if let task = grid.active {
                            Text("Finishing image \(task.variant + 1)").font(.subheadline)
                            ProgressView(value: grid.progress).tint(GridStyle.orange)
                        } else if grid.sharing {
                            Text("Ready to help").font(.subheadline).foregroundStyle(GridStyle.muted)
                        }
                        Toggle(isOn: Binding(get: { grid.sharing }, set: { enabled in
                            Task {
                                if enabled { await grid.start() }
                                else { await grid.pause() }
                            }
                        })) {
                            HStack {
                                Text("Finish images").font(.headline)
                                if grid.contributionTransition { ProgressView().controlSize(.small) }
                            }
                        }.tint(GridStyle.orange)
                            .disabled(!grid.sharing && (grid.busy || grid.contributionTransition))
                            .accessibilityHint("Turn on to start sharing. Turn off to pause.")
                        Text("Leaving the app pauses sharing.").font(.caption).foregroundStyle(GridStyle.muted)
                        Stepper("Stop after \(grid.limits.session_minutes) min", value: $grid.limits.session_minutes, in: 5...120, step: 5)
                            .font(.subheadline).disabled(grid.sharing || grid.contributionTransition)
                    }.gridPanel()
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
                    NavigationLink {
                        DeveloperOptionsView()
                    } label: {
                        Label("Developer options", systemImage: "slider.horizontal.3")
                    }
                }
                Section("Activity") {
                    if grid.snapshot?.events.isEmpty == true { Text("Nothing yet").foregroundStyle(GridStyle.muted) }
                    ForEach(grid.snapshot?.events ?? []) { event in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(event.message)
                            Text(Date(timeIntervalSince1970: event.created_at), style: .time).font(.caption).foregroundStyle(GridStyle.muted)
                        }
                    }
                }
                Section { Button("Disconnect this phone", role: .destructive) { Task { await grid.disconnect() } } }
            }.navigationTitle("Activity").navigationBarTitleDisplayMode(.inline)
                .scrollContentBackground(.hidden).background(GridStyle.background).refreshable { await grid.refresh() }
        }
    }
}

private struct DeveloperOptionsView: View {
    @EnvironmentObject private var grid: GridModel
    @AppStorage("gipu.developerOptionsEnabled") private var enabled = false
    @AppStorage("gipu.usePlanner") private var useAgent = false

    var body: some View {
        Form {
            Section {
                Toggle("Developer options", isOn: $enabled).tint(GridStyle.orange)
            } footer: {
                Text("Saved on this device. Turning this on does not start sharing.")
            }
            if enabled {
                Section {
                    LabeledContent("CPU threads", value: "1")
                    Picker("Maximum image", selection: $grid.limits.max_pixels) {
                        Text("256 × 256").tag(65536)
                        Text("384 × 384").tag(147456)
                        Text("512 × 512").tag(262144)
                    }.disabled(grid.sharing || grid.contributionTransition)
                } header: { Text("Image finishing") } footer: {
                    Text(grid.sharing ? "Pause finishing to change limits." : "One image at a time. Image limits are not memory or GPU caps.")
                }
                Section("Device status") {
                    LabeledContent("Stage", value: grid.stage)
                    LabeledContent("Backend", value: grid.ownDevice?.telemetry?.backend ?? "—")
                    if grid.active != nil {
                        LabeledContent("Task progress", value: grid.progress.formatted(.percent.precision(.fractionLength(0))))
                    }
                    Text("This phone finishes laptop images. It does not generate them.").font(.footnote).foregroundStyle(GridStyle.muted)
                }
                Section {
                    Toggle("Smart device selection", isOn: $useAgent)
                        .tint(GridStyle.orange).disabled(!useAgent && grid.snapshot?.agent.available != true)
                    LabeledContent("Planner", value: grid.snapshot?.agent.mode ?? "—")
                } header: { Text("Requests") } footer: {
                    Text("Applies to new requests while Developer options is on.")
                }
                Section("Device details") {
                    ForEach(grid.snapshot?.devices ?? []) { device in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(device.name)
                            Text(sharingStatus(device)).font(.caption).foregroundStyle(GridStyle.muted)
                            Text(device.capabilities?.joined(separator: ", ") ?? "Capabilities unavailable")
                                .font(.caption).foregroundStyle(GridStyle.muted)
                        }.padding(.vertical, 4)
                    }
                }
                Section("Request details") {
                    ForEach(grid.ownJobs) { job in
                        DisclosureGroup(job.prompt) {
                            if let planning = job.plan?.planning?.status {
                                LabeledContent("Planning", value: planning).font(.subheadline)
                            }
                            ForEach(job.tasks) { task in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("\(task.kind == "image_generate" ? "Create" : "Finish") · image \(task.variant + 1)")
                                    Text("\(task.device_id.flatMap { id in grid.snapshot?.devices.first { $0.id == id }?.name } ?? "Awaiting device") · \(task.status)")
                                        .font(.caption).foregroundStyle(GridStyle.muted)
                                }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 6)
                            }
                        }
                    }
                }
                Section("Grid") {
                    Text(grid.server).font(.footnote).textSelection(.enabled)
                }
            }
        }.navigationTitle("Developer options").navigationBarTitleDisplayMode(.inline)
            .scrollContentBackground(.hidden).background(GridStyle.background)
    }

    private func sharingStatus(_ device: Device) -> String {
        guard device.online else { return "Offline" }
        guard device.enabled else { return "Connected · paused" }
        guard let now = grid.snapshot?.server_time, let expiry = device.session_expires_at else { return "Checking session…" }
        return expiry > now ? (device.active_task_id == nil ? "Sharing · ready" : "Sharing · working") : "Connected · session ended"
    }
}
