import Foundation

/// The discouraging copy shown on the shield. Kept in the shared target so the
/// app can preview it and the extension can render it.
enum Deterrents {
    static let titles: [String] = [
        "Точно хочешь открыть?",
        "Секунду — зачем?",
        "Ещё раз пролистать ленту?",
        "Стоп. Подумай.",
    ]

    static let messages: [String] = [
        "Ты открываешь Instagram на автомате. Через 20 минут ты не вспомнишь ни одного поста, а время не вернёшь.",
        "Чего ты сейчас на самом деле хочешь? Отдохнуть, отвлечься или занять руки? Лента ничего из этого не даёт.",
        "Ты заходил сюда недавно. За это время ничего важного не появилось.",
        "Представь, что закроешь телефон прямо сейчас и займёшься тем, что откладывал. Приятно, да?",
        "Лайки чужих жизней не сделают твою лучше. Займись своей.",
        "Тот, кем ты хочешь стать, сейчас бы не открывал ленту.",
        "Пять минут тишины лучше, чем полчаса чужого шума.",
        "Ничего не случится, если ты не проверишь ленту. Правда ничего.",
    ]

    static func randomTitle() -> String { titles.randomElement() ?? titles[0] }
    static func randomMessage() -> String { messages.randomElement() ?? messages[0] }
}
