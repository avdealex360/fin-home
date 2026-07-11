import ManagedSettings
import Foundation

/// Handles taps on the shield's two buttons.
class ShieldActionProvider: ShieldActionDelegate {
    /// How long "open anyway" lifts the shield before it snaps back.
    private let bypassWindow: TimeInterval = 5 * 60

    override func handle(action: ShieldAction,
                         for application: ApplicationToken,
                         completionHandler: @escaping (ShieldActionResponse) -> Void) {
        completionHandler(respond(to: action))
    }

    override func handle(action: ShieldAction,
                         for webDomain: WebDomainToken,
                         completionHandler: @escaping (ShieldActionResponse) -> Void) {
        completionHandler(respond(to: action))
    }

    override func handle(action: ShieldAction,
                         for category: ActivityCategoryToken,
                         completionHandler: @escaping (ShieldActionResponse) -> Void) {
        completionHandler(respond(to: action))
    }

    private func respond(to action: ShieldAction) -> ShieldActionResponse {
        switch action {
        case .primaryButtonPressed:
            // "Передумал" — keep the shield up, send the user back to the Home Screen.
            StatsStore.mutate { $0.timesReconsidered += 1 }
            return .close
        case .secondaryButtonPressed:
            // "Всё равно открыть" — grant a short grace window, then let it back.
            StatsStore.mutate { $0.timesOpenedAnyway += 1 }
            AppStorageGateway.bypassUntil = Date().addingTimeInterval(bypassWindow)
            ShieldManager.clear()
            return .none
        @unknown default:
            return .close
        }
    }
}
