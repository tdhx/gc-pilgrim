import Foundation

public struct CalendarFeed: Codable, Sendable, Equatable {
    public static let supportedSchemaVersion = 1

    public let schemaVersion: Int
    public let generatedAt: Date
    public let timezone: String
    public let coverage: Coverage
    public let sources: [SourceSummary]
    public let warnings: [String]
    public let events: [CalendarEvent]

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case generatedAt = "generated_at"
        case timezone, coverage, sources, warnings, events
    }

    public func validate() throws {
        guard schemaVersion == Self.supportedSchemaVersion else {
            throw FeedError.unsupportedSchema(schemaVersion)
        }
        guard coverage.start <= coverage.end else { throw FeedError.invalidCoverage }
        guard Set(events.map(\.id)).count == events.count else {
            throw FeedError.duplicateEventID
        }
        guard events == events.sorted(by: CalendarEvent.chronological) else {
            throw FeedError.unsortedEvents
        }
    }
}

public struct Coverage: Codable, Sendable, Equatable {
    public let start: String
    public let end: String
}

public struct SourceSummary: Codable, Sendable, Equatable, Identifiable {
    public var id: String { name }
    public let name: String
    public let url: URL?
    public let status: String
}

public struct CalendarEvent: Codable, Sendable, Equatable, Identifiable {
    public let id: String
    public let start: String
    public let end: String
    public let allDay: Bool
    public let timezone: String
    public let church: String?
    public let eventType: String
    public let eventSubtype: String?
    public let associatedDevotions: [String]
    public let serviceName: String
    public let title: String
    public let presiders: [String]
    public let location: String?
    public let description: String?
    public let sourceID: String
    public let liturgicalDate: String?
    public let liturgical: LiturgicalRecord?

    enum CodingKeys: String, CodingKey {
        case id, start, end, timezone, church, title, presiders, location, description, liturgical
        case allDay = "all_day"
        case eventType = "event_type"
        case eventSubtype = "event_subtype"
        case associatedDevotions = "associated_devotions"
        case serviceName = "service_name"
        case sourceID = "source_id"
        case liturgicalDate = "liturgical_date"
    }

    public static func chronological(_ lhs: Self, _ rhs: Self) -> Bool {
        (lhs.start, lhs.end, lhs.title) < (rhs.start, rhs.end, rhs.title)
    }

    public var displayTitle: String { liturgical?.observance ?? serviceName }
    public var displayChurch: String { church ?? "Unassigned" }
    public var isVigil: Bool { serviceName == "Vigil Mass" }
}

public struct LiturgicalRecord: Codable, Sendable, Equatable {
    public let date: String
    public let observance: String
    public let rank: String?
    public let season: String?
    public let seasonWeek: Int?
    public let liturgicalColour: String?
    public let psalmWeek: Int?
    public let alternatives: [String]
    public let sourceURL: URL?

    enum CodingKeys: String, CodingKey {
        case date, observance, rank, season, alternatives
        case seasonWeek = "season_week"
        case liturgicalColour = "liturgical_colour"
        case psalmWeek = "psalm_week"
        case sourceURL = "source_url"
    }
}

public enum FeedError: LocalizedError, Equatable {
    case unsupportedSchema(Int)
    case invalidCoverage
    case duplicateEventID
    case unsortedEvents
    case missingFeedURL
    case invalidResponse

    public var errorDescription: String? {
        switch self {
        case .unsupportedSchema(let version):
            "This app cannot read calendar schema version \(version)."
        case .invalidCoverage:
            "The calendar feed has invalid coverage dates."
        case .duplicateEventID:
            "The calendar feed contains duplicate events."
        case .unsortedEvents:
            "The calendar feed is not ordered chronologically."
        case .missingFeedURL:
            "The calendar feed URL is not configured."
        case .invalidResponse:
            "The calendar server returned an invalid response."
        }
    }
}

public extension JSONDecoder {
    static var calendarFeed: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }
}
