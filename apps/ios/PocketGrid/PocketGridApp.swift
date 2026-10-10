import SwiftUI
import UserNotifications

final class NotificationDelegate: NSObject, UNUserNotificationCenterDelegate {
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound])
    }
}

@main
struct PocketGridApp: App {
    @StateObject private var grid = GridModel()
    @Environment(\.scenePhase) private var scenePhase
    private let notifications = NotificationDelegate()
    init() { UNUserNotificationCenter.current().delegate = notifications }
    var body: some Scene {
        WindowGroup {
            ContentView().environmentObject(grid)
                .tint(Color(red: 0.05, green: 0.48, blue: 0.39))
                .onChange(of: scenePhase) { _, phase in grid.setForeground(phase == .active) }
        }
    }
}
