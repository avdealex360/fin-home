import Foundation
import FamilyControls
import ManagedSettings

/// Applies and removes the shield on the selected apps. Shared by the app
/// (when the user toggles protection) and the device-activity monitor
/// (when a temporary bypass expires).
enum ShieldManager {
    private static var store: ManagedSettingsStore { ManagedSettingsStore(named: .deterrent) }

    static func apply(_ selection: FamilyActivitySelection) {
        let apps = selection.applicationTokens
        let categories = selection.categoryTokens
        let domains = selection.webDomainTokens

        store.shield.applications = apps.isEmpty ? nil : apps
        store.shield.applicationCategories = categories.isEmpty ? nil : .specific(categories)
        store.shield.webDomains = domains.isEmpty ? nil : domains
    }

    static func clear() {
        store.shield.applications = nil
        store.shield.applicationCategories = nil
        store.shield.webDomains = nil
    }

    /// Re-apply the stored selection if guarding is on and no bypass is active.
    static func refreshFromStorage() {
        guard AppStorageGateway.isGuarding else { clear(); return }
        if let until = AppStorageGateway.bypassUntil, until > Date() { return }
        AppStorageGateway.bypassUntil = nil
        apply(AppStorageGateway.loadSelection())
    }
}
