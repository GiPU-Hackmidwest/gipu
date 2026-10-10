import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var grid: GridModel
    var body: some View {
        Group {
            if grid.connected {
                TabView {
                    CreateView().tabItem { Label("Create", systemImage: "photo") }
                    ContributeView().tabItem { Label("Contribute", systemImage: "cpu") }
                    ActivityView().tabItem { Label("Activity", systemImage: "bell") }
                }
            } else { JoinView() }
        }
        .alert("PocketGrid", isPresented: Binding(get: { grid.error != nil }, set: { if !$0 { grid.error = nil } })) {
            Button("OK") { grid.error = nil }
        } message: { Text(grid.error ?? "") }
    }
}

private struct JoinView: View {
    @EnvironmentObject private var grid: GridModel
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Turn spare device time into finished work.").font(.title2.bold())
                    Text("Request images generated on participating laptops. This phone can contribute the final image processing step.")
                }
                Section {
                    TextField("Coordinator URL", text: $grid.server).textContentType(.URL).keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    TextField("Your device name", text: $grid.name)
                    SecureField("Join code", text: $grid.joinCode).textInputAutocapitalization(.never)
                    Button { Task { await grid.join() } } label: {
                        HStack { Text("Join grid"); Spacer(); if grid.busy { ProgressView() } }
                    }.disabled(grid.busy || grid.name.trimmingCharacters(in: .whitespaces).isEmpty)
                } header: { Text("Join your demo grid") } footer: {
                    Text("On a physical phone, use your coordinator’s LAN IP, such as http://192.168.1.20:8787. Contribution starts only when you tap Start.")
                }
                Section {
                    Text("Use public demo prompts and images. Members and workers of this invite-only grid can see assigned inputs. Credits are sandbox units with no cash value.").font(.footnote)
                }
            }.navigationTitle("PocketGrid")
        }
    }
}

private struct BalanceView: View {
    @EnvironmentObject private var grid: GridModel
    var body: some View {
        HStack(alignment: .top) {
            metric("Available", grid.snapshot?.balance ?? 0)
            Spacer()
            metric("Reserved", grid.snapshot?.reserved ?? 0)
            Spacer()
            metric("Earned", grid.snapshot?.earned ?? 0)
        }
        .accessibilityElement(children: .combine)
    }
    private func metric(_ label: String, _ value: Int) -> some View {
        VStack(alignment: .leading) { Text("\(value)").font(.title2.monospacedDigit().bold()); Text(label).font(.caption).foregroundStyle(.secondary) }
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
            List {
                Section("Sandbox credits") { BalanceView() }
                Section {
                    TextField("Describe your image", text: $prompt, axis: .vertical).lineLimit(2...5)
                    Stepper("Images: \(count)", value: $count, in: 1...4)
                        .onChange(of: count) { _, value in budget = max(budget, value * 7 + 1) }
                    Stepper("Budget: \(budget) credits", value: $budget, in: (count * 7 + 1)...100)
                    Text("Quote: \(count * 7 + 1) credits · 256 × 256 · 12 steps").font(.caption).foregroundStyle(.secondary)
                    Toggle("Plan with AWS Strands", isOn: $useAgent).disabled(grid.snapshot?.agent.available != true)
                    Text("\(grid.snapshot?.agent.mode ?? "Checking") agent mode").font(.caption).foregroundStyle(.secondary)
                    Button { Task { await grid.submit(prompt: prompt, count: count, budget: budget, useAgent: useAgent) } } label: {
                        HStack { Text("Generate on the grid"); Spacer(); if grid.busy { ProgressView() } }
                    }.disabled(grid.busy || prompt.trimmingCharacters(in: .whitespaces).isEmpty)
                } header: { Text("Make an image") } footer: {
                    Text("A participating laptop runs the image model. Phones finish exports. The whole budget is reserved; unused credits return when the job finishes or is cancelled.")
                }
                if let notice = grid.notice { Section { Text(notice).font(.footnote) } }
                ForEach(grid.ownJobs) { job in
                    Section {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(job.prompt).font(.headline)
                            Text(job.status.capitalized).foregroundStyle(.secondary)
                            ProgressView(value: Double(job.tasks.filter { $0.status == "completed" }.count), total: Double(max(1, job.tasks.count)))
                            ForEach(job.images) { item in ProtectedImage(path: item.url, stage: item.stage) }
                            if let receipt = job.receipt {
                                Text("Receipt · workers \(receipt.contributor_total) + service \(receipt.platform_fee) = \(receipt.total_charged) charged. \(receipt.refund) returned.").font(.caption)
                            } else {
                                Text("Budget \(job.budget) · spent \(job.spent) · refunded \(job.refunded)").font(.caption)
                            }
                            if ["queued", "running"].contains(job.status) { Button("Cancel request", role: .destructive) { Task { await grid.cancel(job) } } }
                        }
                    }
                }
            }
            .navigationTitle("Create")
            .refreshable { await grid.refresh() }
        }
    }
}

private struct ProtectedImage: View {
    @EnvironmentObject private var grid: GridModel
    let path: String
    let stage: String
    @State private var image: UIImage?
    @State private var failed = false
    var body: some View {
        VStack(alignment: .leading) {
            if let image { Image(uiImage: image).resizable().scaledToFit().frame(maxHeight: 280).accessibilityLabel("Grid generated image") }
            else if failed { Label("Image unavailable", systemImage: "photo.badge.exclamationmark") }
            else { ProgressView() }
            Text(stage.replacingOccurrences(of: "_", with: " ").capitalized).font(.caption).foregroundStyle(.secondary)
        }.task(id: path) {
            do { image = UIImage(data: try await grid.image(path)); failed = image == nil }
            catch { failed = true }
        }
    }
}

private struct ContributeView: View {
    @EnvironmentObject private var grid: GridModel
    var body: some View {
        NavigationStack {
            Form {
                Section("This phone") {
                    Label(grid.sharing ? "Sharing while open" : "Paused", systemImage: grid.sharing ? "cpu.fill" : "pause.circle")
                        .font(.headline)
                    Text(grid.stage)
                    if let task = grid.active {
                        Text("Image \(task.variant + 1) · \(task.width) × \(task.height) · \(task.price) credit(s)").font(.caption)
                        ProgressView(value: grid.progress)
                    }
                    LabeledContent("Earned on this device", value: "\(grid.ownDevice?.earned ?? 0) credits")
                    if let expires = grid.ownDevice?.session_expires_at, grid.sharing {
                        LabeledContent("Session ends", value: Date(timeIntervalSince1970: expires).formatted(date: .omitted, time: .shortened))
                    }
                }
                Section {
                    Stepper("Maximum CPU threads: \(grid.limits.cpu_threads)", value: $grid.limits.cpu_threads, in: 1...4)
                    Picker("Maximum image", selection: $grid.limits.max_pixels) {
                        Text("256 × 256").tag(65536)
                        Text("384 × 384").tag(147456)
                        Text("512 × 512").tag(262144)
                    }
                    Stepper("Session: \(grid.limits.session_minutes) minutes", value: $grid.limits.session_minutes, in: 5...120, step: 5)
                } header: { Text("Workload limits") } footer: {
                    Text("One image at a time, one CPU thread for pixel processing. The thread setting is an upper bound, not a device-wide CPU percentage. Pause before changing limits.")
                }.disabled(grid.sharing || grid.contributionTransition)
                Section {
                    if grid.sharing {
                        Button("Pause contribution", role: .destructive) { Task { await grid.pause() } }
                    } else {
                        Button("Start contributing") { Task { await grid.start() } }.disabled(grid.busy || grid.contributionTransition)
                    }
                } footer: {
                    Text("Keep PocketGrid open to contribute. Locking your phone or leaving the app stops its work. Unfinished work returns to the grid. No credits are paid for partial results.")
                }
                Section("Actual work on this phone") {
                    Text("Download an image generated by a laptop, add its four-pixel export frame using this phone’s CPU, then upload the result. The coordinator checks every output pixel before accepting and paying for the work.").font(.footnote)
                }
            }.navigationTitle("Contribute")
        }
    }
}

private struct ActivityView: View {
    @EnvironmentObject private var grid: GridModel
    var body: some View {
        NavigationStack {
            List {
                Section("Account") {
                    Text(grid.snapshot?.user.name ?? "Connecting")
                    BalanceView()
                    Button("Enable notifications · \(grid.notificationStatus)") { Task { await grid.enableNotifications() } }
                    Text("Notifications cover work starting, accepted credits, and finished jobs while the app receives updates. This prototype does not deliver remote push notifications after the app closes.").font(.caption).foregroundStyle(.secondary)
                }
                Section("Grid activity") {
                    ForEach(grid.snapshot?.events ?? []) { event in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(event.message)
                            Text(Date(timeIntervalSince1970: event.created_at), style: .time).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
                Section("Devices") {
                    ForEach(grid.snapshot?.devices ?? []) { device in
                        VStack(alignment: .leading) {
                            Text(device.name)
                            Text("\(device.kind) · \(device.online ? "online" : "offline") · \(device.enabled ? "enabled" : "paused")").font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
                Section { Button("Disconnect this phone", role: .destructive) { Task { await grid.disconnect() } } }
            }.navigationTitle("Activity").refreshable { await grid.refresh() }
        }
    }
}
