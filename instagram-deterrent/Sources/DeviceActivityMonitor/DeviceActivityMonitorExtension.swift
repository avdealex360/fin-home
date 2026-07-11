import DeviceActivity

/// Optional: re-applies shields at schedule boundaries so a temporary
/// "open anyway" bypass is automatically revoked even if the user never
/// re-opens the main app.
class DeviceActivityMonitorExtension: DeviceActivityMonitor {
    override func intervalDidStart(for activity: DeviceActivityName) {
        super.intervalDidStart(for: activity)
        ShieldManager.refreshFromStorage()
    }

    override func intervalDidEnd(for activity: DeviceActivityName) {
        super.intervalDidEnd(for: activity)
        ShieldManager.refreshFromStorage()
    }

    override func eventDidReachThreshold(_ event: DeviceActivityEvent.Name,
                                         activity: DeviceActivityName) {
        super.eventDidReachThreshold(event, activity: activity)
        ShieldManager.refreshFromStorage()
    }
}
