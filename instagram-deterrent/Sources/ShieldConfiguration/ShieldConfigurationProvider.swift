import ManagedSettings
import ManagedSettingsUI
import UIKit

/// Builds the custom screen iOS shows when a shielded app is opened.
class ShieldConfigurationProvider: ShieldConfigurationDataSource {
    override func configuration(shielding application: Application) -> ShieldConfiguration {
        makeConfiguration()
    }

    override func configuration(shielding application: Application,
                                in category: ActivityCategory) -> ShieldConfiguration {
        makeConfiguration()
    }

    override func configuration(shielding webDomain: WebDomain) -> ShieldConfiguration {
        makeConfiguration()
    }

    override func configuration(shielding webDomain: WebDomain,
                                in category: ActivityCategory) -> ShieldConfiguration {
        makeConfiguration()
    }

    private func makeConfiguration() -> ShieldConfiguration {
        StatsStore.mutate { $0.timesConsidered += 1 }

        let background = UIColor(red: 0.05, green: 0.05, blue: 0.09, alpha: 1)
        let accent = UIColor(red: 0.29, green: 0.56, blue: 0.95, alpha: 1)

        return ShieldConfiguration(
            backgroundBlurStyle: .systemUltraThinMaterialDark,
            backgroundColor: background,
            icon: UIImage(systemName: "hand.raised.fill"),
            title: .init(text: Deterrents.randomTitle(), color: .white),
            subtitle: .init(text: Deterrents.randomMessage(), color: UIColor(white: 0.78, alpha: 1)),
            primaryButtonLabel: .init(text: "Передумал", color: .white),
            primaryButtonBackgroundColor: accent,
            secondaryButtonLabel: .init(text: "Всё равно открыть", color: UIColor(white: 0.55, alpha: 1))
        )
    }
}
