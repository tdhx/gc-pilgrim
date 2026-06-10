import Foundation

public struct CalendarFilters: Sendable, Equatable {
    public var eventTypes: Set<String>
    public var multiculturalSubtypes: Set<String>
    public var churches: Set<String>
    public var presiders: Set<String>
    public var search: String

    public init(
        eventTypes: Set<String> = ["mass", "confession"],
        multiculturalSubtypes: Set<String> = [],
        churches: Set<String> = [],
        presiders: Set<String> = [],
        search: String = ""
    ) {
        self.eventTypes = eventTypes
        self.multiculturalSubtypes = multiculturalSubtypes
        self.churches = churches
        self.presiders = presiders
        self.search = search
    }

    public func matches(_ event: CalendarEvent) -> Bool {
        if !eventTypes.isEmpty, !eventTypes.contains(event.eventType) { return false }
        if event.eventType == "multicultural",
           eventTypes.contains("multicultural"),
           !multiculturalSubtypes.isEmpty,
           !multiculturalSubtypes.contains(event.eventSubtype ?? "") {
            return false
        }
        if !churches.isEmpty, !churches.contains(event.displayChurch) { return false }
        if !presiders.isEmpty, event.presiders.allSatisfy({ !presiders.contains($0) }) {
            return false
        }
        let needle = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !needle.isEmpty else { return true }
        let values = [
            event.title,
            event.location,
            event.description,
            event.displayChurch,
            event.serviceName,
            event.liturgical?.observance,
            event.liturgical?.rank,
            event.liturgical?.season
        ].compactMap { $0 } + event.presiders
        return values.joined(separator: " ").lowercased().contains(needle)
    }
}

public struct FilterOptions: Sendable, Equatable {
    public let eventTypes: [String]
    public let multiculturalSubtypes: [String]
    public let churches: [String]
    public let presiders: [String]

    public init(events: [CalendarEvent]) {
        eventTypes = Set(events.map(\.eventType)).sorted()
        multiculturalSubtypes = Set(events.compactMap(\.eventSubtype)).sorted()
        churches = Set(events.map(\.displayChurch)).sorted()
        presiders = Set(events.flatMap(\.presiders)).sorted()
    }
}
