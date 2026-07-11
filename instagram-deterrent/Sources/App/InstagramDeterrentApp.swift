import SwiftUI

@main
struct InstagramDeterrentApp: App {
    @StateObject private var model = ScreenTimeModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(model)
                .preferredColorScheme(.dark)
        }
    }
}
