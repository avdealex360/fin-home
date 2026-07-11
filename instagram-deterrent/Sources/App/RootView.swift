import SwiftUI

struct RootView: View {
    @EnvironmentObject private var model: ScreenTimeModel
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        Group {
            switch model.authorizationStatus {
            case .approved:
                HomeView()
            default:
                OnboardingView()
            }
        }
        .onChange(of: scenePhase) { phase in
            if phase == .active { model.refresh() }
        }
    }
}
