import Foundation
import FamilyControls

/// Thin wrapper over the shared App Group `UserDefaults`, so the app and its
/// extensions read and write the same selection, flags and stats.
enum AppStorageGateway {
    static var defaults: UserDefaults {
        UserDefaults(suiteName: AppGroup.identifier) ?? .standard
    }

    // MARK: Selected apps

    static func loadSelection() -> FamilyActivitySelection {
        guard let data = defaults.data(forKey: StorageKey.selection),
              let selection = try? JSONDecoder().decode(FamilyActivitySelection.self, from: data)
        else { return FamilyActivitySelection() }
        return selection
    }

    static func saveSelection(_ selection: FamilyActivitySelection) {
        guard let data = try? JSONEncoder().encode(selection) else { return }
        defaults.set(data, forKey: StorageKey.selection)
    }

    // MARK: Flags

    static var isGuarding: Bool {
        get { defaults.bool(forKey: StorageKey.isGuarding) }
        set { defaults.set(newValue, forKey: StorageKey.isGuarding) }
    }

    /// While this timestamp is in the future the shield is intentionally lifted
    /// (the user chose "open anyway"). The monitor / app restores it afterwards.
    static var bypassUntil: Date? {
        get {
            let t = defaults.double(forKey: StorageKey.bypassUntil)
            return t > 0 ? Date(timeIntervalSince1970: t) : nil
        }
        set { defaults.set(newValue?.timeIntervalSince1970 ?? 0, forKey: StorageKey.bypassUntil) }
    }
}
