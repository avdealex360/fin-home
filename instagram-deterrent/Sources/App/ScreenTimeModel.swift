import Foundation
import FamilyControls
import Combine

/// Owns Family Controls authorization and mirrors the shared guarding state
/// into the UI. All shield mutations go through `ShieldManager`.
@MainActor
final class ScreenTimeModel: ObservableObject {
    @Published var authorizationStatus: AuthorizationStatus
    @Published var selection: FamilyActivitySelection {
        didSet { AppStorageGateway.saveSelection(selection) }
    }
    @Published private(set) var isGuarding: Bool
    @Published private(set) var stats: DeterrentStats

    private let center = AuthorizationCenter.shared

    init() {
        authorizationStatus = AuthorizationCenter.shared.authorizationStatus
        selection = AppStorageGateway.loadSelection()
        isGuarding = AppStorageGateway.isGuarding
        stats = StatsStore.load()
    }

    var hasSelection: Bool {
        !selection.applicationTokens.isEmpty
            || !selection.categoryTokens.isEmpty
            || !selection.webDomainTokens.isEmpty
    }

    func requestAuthorization() async {
        do {
            try await center.requestAuthorization(for: .individual)
        } catch {
            print("Family Controls authorization failed: \(error)")
        }
        authorizationStatus = center.authorizationStatus
    }

    /// Called whenever the app returns to the foreground.
    func refresh() {
        authorizationStatus = center.authorizationStatus
        isGuarding = AppStorageGateway.isGuarding
        stats = StatsStore.load()
        ShieldManager.refreshFromStorage()
    }

    func startGuarding() {
        guard hasSelection else { return }
        AppStorageGateway.isGuarding = true
        AppStorageGateway.bypassUntil = nil
        ShieldManager.apply(selection)
        isGuarding = true
    }

    func stopGuarding() {
        AppStorageGateway.isGuarding = false
        ShieldManager.clear()
        isGuarding = false
    }
}
