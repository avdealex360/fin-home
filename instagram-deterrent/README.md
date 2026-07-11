# Меньше ленты — Instagram Deterrent

iOS-приложение, которое **отговаривает открывать Instagram**. Каждый раз, когда
ты тапаешь по иконке Instagram, система показывает не ленту, а полноэкранное
напоминание с мягким «а зачем?» и двумя кнопками: **«Передумал»** и
**«Всё равно открыть»**.

> Проект отпочковался от эксперимента в репозитории `fin-home` и лежит в папке
> `instagram-deterrent/`. Это самостоятельное приложение — папку можно вынести в
> отдельный git-репозиторий (`git init`) без изменений.

## Как это работает

В iOS обычное приложение **не может** «поймать» запуск другого приложения.
Единственный санкционированный Apple способ — **Screen Time API** (семейство
фреймворков Family Controls):

| Фреймворк              | Роль здесь                                                            |
| ---------------------- | -------------------------------------------------------------------- |
| **FamilyControls**     | запрос разрешения + пикер, в котором пользователь выбирает Instagram  |
| **ManagedSettings**    | ставит «щит» (shield) на выбранные приложения                        |
| **ManagedSettingsUI**  | рисует кастомный экран поверх заблокированного приложения             |
| **DeviceActivity**     | восстанавливает щит после временного «Всё равно открыть»              |

Когда на Instagram стоит щит, при открытии система показывает наш
`ShieldConfiguration` (текст-отговорку из `Deterrents.swift`), а нажатия по его
кнопкам обрабатывает `ShieldAction`.

## Архитектура

```
Sources/
  Shared/                     ← код, общий для приложения и расширений
    Constants.swift             App Group id, имя ManagedSettingsStore
    AppStorageGateway.swift     чтение/запись в общий App Group UserDefaults
    Stats.swift                 счётчики (показов / передумал / открыл)
    Deterrents.swift            тексты-отговорки
    ShieldManager.swift         apply / clear / restore щита
  App/                        ← основное SwiftUI-приложение
    InstagramDeterrentApp.swift
    ScreenTimeModel.swift       авторизация Family Controls + состояние
    RootView / OnboardingView / HomeView
  ShieldConfiguration/        ← app-extension: кастомный экран-отговорка
  ShieldAction/               ← app-extension: обработка кнопок щита
  DeviceActivityMonitor/      ← app-extension: авто-возврат щита
project.yml                   ← спека XcodeGen (генерит .xcodeproj)
```

Расширения общаются с приложением через **App Group** (`group.com.avdealex.instagramdeterrent`):
выбор приложений, флаг защиты и статистика лежат в общем `UserDefaults`.

## Требования

- Xcode 15+, iOS 16.0+
- **Настоящее устройство** — Family Controls не работает в симуляторе
- Apple Developer account (capability **Family Controls**)
- [XcodeGen](https://github.com/yonyz/XcodeGen) — генерирует `.xcodeproj` из `project.yml`

## Сборка

```bash
brew install xcodegen          # если ещё не стоит
cd instagram-deterrent
xcodegen generate              # создаёт InstagramDeterrent.xcodeproj
open InstagramDeterrent.xcodeproj
```

Затем в Xcode:

1. Впиши свой **Team** во все таргеты (или заполни `DEVELOPMENT_TEAM` в `project.yml`
   и перегенерируй).
2. Проверь, что у всех четырёх таргетов включены capability **Family Controls** и
   **App Groups** с одной и той же группой (`.entitlements` уже настроены).
3. Собери на реальном iPhone.

При первом запуске приложение попросит разрешение на Экранное время, затем
предложит выбрать приложения (выбери Instagram) и включить защиту.

> **Family Controls entitlement.** В режиме разработки хватает Development-варианта
> capability. Для публикации в App Store нужно
> [запросить у Apple](https://developer.apple.com/contact/request/family-controls-distribution)
> распределяемый entitlement.

## Известные ограничения

- **«Всё равно открыть»** снимает щит на 5 минут (`bypassWindow` в
  `ShieldActionProvider`). Автоматически он возвращается, когда срабатывает
  `DeviceActivityMonitor` или когда пользователь снова открывает наше приложение.
  Для жёсткого таймера на 5 минут нужно завести расписание `DeviceActivity`
  (`DeviceActivityCenter().startMonitoring(...)`) — заготовка расширения уже есть.
- Bundle id и App Group завязаны на префикс `com.avdealex` — поменяй под свой
  Team, если нужно (в `project.yml` и во всех `.entitlements`/`Constants.swift`).
