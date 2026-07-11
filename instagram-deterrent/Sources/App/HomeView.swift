import SwiftUI
import FamilyControls

struct HomeView: View {
    @EnvironmentObject private var model: ScreenTimeModel
    @State private var showPicker = false

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Toggle(isOn: Binding(
                        get: { model.isGuarding },
                        set: { $0 ? model.startGuarding() : model.stopGuarding() }
                    )) {
                        Label("Защита включена", systemImage: "shield.fill")
                    }
                    .disabled(!model.hasSelection)

                    Button {
                        showPicker = true
                    } label: {
                        Label(model.hasSelection ? "Изменить приложения" : "Выбрать приложения",
                              systemImage: "app.badge")
                    }
                } header: {
                    Text("Защита")
                } footer: {
                    Text(model.hasSelection
                         ? "Выбранные приложения будут показывать экран-напоминание при открытии."
                         : "Выбери Instagram (или другие приложения), которые хочешь ограничить.")
                }

                Section("Статистика") {
                    statRow("Показов напоминания", "\(model.stats.timesConsidered)")
                    statRow("Передумал", "\(model.stats.timesReconsidered)")
                    statRow("Всё равно открыл", "\(model.stats.timesOpenedAnyway)")
                    if model.stats.timesConsidered > 0 {
                        statRow("Удержался", "\(Int(model.stats.successRate * 100))%")
                    }
                }
            }
            .navigationTitle("Меньше ленты")
            .familyActivityPicker(isPresented: $showPicker, selection: $model.selection)
            .onChange(of: showPicker) { presented in
                // Re-apply shields to the freshly picked set while protection is on.
                if !presented && model.isGuarding { model.startGuarding() }
            }
        }
    }

    private func statRow(_ title: String, _ value: String) -> some View {
        HStack {
            Text(title)
            Spacer()
            Text(value).foregroundStyle(.secondary).monospacedDigit()
        }
    }
}
