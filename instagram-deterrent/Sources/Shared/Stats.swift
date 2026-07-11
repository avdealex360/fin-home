import Foundation

/// Lightweight counters shown on the home screen. Stored in the App Group so
/// the shield-action extension can bump them too.
struct DeterrentStats: Codable, Equatable {
    var timesConsidered = 0    // the shield was shown
    var timesReconsidered = 0  // user backed out ("changed my mind")
    var timesOpenedAnyway = 0  // user pushed through

    static let empty = DeterrentStats()

    var successRate: Double {
        guard timesConsidered > 0 else { return 0 }
        return Double(timesReconsidered) / Double(timesConsidered)
    }
}

enum StatsStore {
    static func load() -> DeterrentStats {
        guard let data = AppStorageGateway.defaults.data(forKey: StorageKey.stats),
              let stats = try? JSONDecoder().decode(DeterrentStats.self, from: data)
        else { return .empty }
        return stats
    }

    static func save(_ stats: DeterrentStats) {
        guard let data = try? JSONEncoder().encode(stats) else { return }
        AppStorageGateway.defaults.set(data, forKey: StorageKey.stats)
    }

    static func mutate(_ transform: (inout DeterrentStats) -> Void) {
        var stats = load()
        transform(&stats)
        save(stats)
    }
}
