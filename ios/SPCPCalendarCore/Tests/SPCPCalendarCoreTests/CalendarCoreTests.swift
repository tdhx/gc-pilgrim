import Foundation
import Testing
@testable import SPCPCalendarCore

@Test func fixtureDecodesAndValidates() throws {
    let url = try #require(Bundle.module.url(forResource: "calendar", withExtension: "json", subdirectory: "Fixtures"))
    let feed = try JSONDecoder.calendarFeed.decode(CalendarFeed.self, from: Data(contentsOf: url))
    try feed.validate()
    #expect(feed.events.count == 2)
    #expect(feed.events[0].displayTitle == "The Epiphany of the Lord")
}

@Test func filtersMatchWebSemantics() throws {
    let url = try #require(Bundle.module.url(forResource: "calendar", withExtension: "json", subdirectory: "Fixtures"))
    let feed = try JSONDecoder.calendarFeed.decode(CalendarFeed.self, from: Data(contentsOf: url))
    var filters = CalendarFilters()
    #expect(feed.events.filter(filters.matches).count == 1)
    filters.eventTypes = ["multicultural"]
    filters.multiculturalSubtypes = ["polish"]
    filters.search = "jerzy"
    #expect(feed.events.filter(filters.matches).map(\.serviceName) == ["Polish Mass"])
}

@Test func unsupportedSchemaDoesNotReplaceCache() throws {
    let directory = FileManager.default.temporaryDirectory.appending(path: UUID().uuidString)
    let cache = FeedCache(fileURL: directory.appending(path: "calendar.json"))
    let valid = fixtureData()
    _ = try cache.saveValidated(valid)
    let invalid = Data(String(decoding: valid, as: UTF8.self)
        .replacingOccurrences(of: "\"schema_version\": 1", with: "\"schema_version\": 2").utf8)
    #expect(throws: FeedError.unsupportedSchema(2)) {
        _ = try cache.saveValidated(invalid)
    }
    #expect(try cache.load().feed.schemaVersion == 1)
}

private func fixtureData() -> Data {
    let url = Bundle.module.url(forResource: "calendar", withExtension: "json", subdirectory: "Fixtures")!
    return try! Data(contentsOf: url)
}
