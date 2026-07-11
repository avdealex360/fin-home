import SwiftUI

struct OnboardingView: View {
    @EnvironmentObject private var model: ScreenTimeModel

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "hand.raised.fill")
                .font(.system(size: 64))
                .foregroundStyle(.tint)

            Text("Меньше Instagram —\nбольше жизни")
                .font(.largeTitle.bold())
                .multilineTextAlignment(.center)

            Text("Приложение показывает экран-напоминание каждый раз, когда ты пытаешься открыть Instagram, и мягко отговаривает.")
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            Spacer()

            if model.authorizationStatus == .denied {
                Text("Доступ к экранному времени запрещён. Включите его в Настройки → Экранное время.")
                    .font(.footnote)
                    .foregroundStyle(.red)
                    .multilineTextAlignment(.center)
            }

            Button {
                Task { await model.requestAuthorization() }
            } label: {
                Text("Разрешить и начать")
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }
}
