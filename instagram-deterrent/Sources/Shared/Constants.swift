import Foundation
import ManagedSettings

/// Shared identifiers used by the app and all of its extensions.
enum AppGroup {
    /// Must match the App Group capability added to every target.
    static let identifier = "group.com.avdealex.instagramdeterrent"
}

extension ManagedSettingsStore.Name {
    /// A named store so the app, the shield action, and the monitor all touch
    /// the same set of shields.
    static let deterrent = Self("deterrent")
}

enum StorageKey {
    static let selection = "familyActivitySelection"
    static let isGuarding = "isGuarding"
    static let stats = "deterrentStats"
    static let bypassUntil = "bypassUntil"
}
