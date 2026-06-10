import Foundation

public struct FeedCache: Sendable {
    public let fileURL: URL

    public init(fileURL: URL) {
        self.fileURL = fileURL
    }

    public func load() throws -> (feed: CalendarFeed, modified: Date) {
        let data = try Data(contentsOf: fileURL)
        let feed = try JSONDecoder.calendarFeed.decode(CalendarFeed.self, from: data)
        try feed.validate()
        let values = try fileURL.resourceValues(forKeys: [.contentModificationDateKey])
        return (feed, values.contentModificationDate ?? .distantPast)
    }

    public func saveValidated(_ data: Data) throws -> CalendarFeed {
        let feed = try JSONDecoder.calendarFeed.decode(CalendarFeed.self, from: data)
        try feed.validate()
        try FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try data.write(to: fileURL, options: .atomic)
        return feed
    }
}

public struct CalendarRepository: Sendable {
    public let feedURL: URL
    public let cache: FeedCache
    public let session: URLSession
    public let staleInterval: TimeInterval

    public init(
        feedURL: URL,
        cache: FeedCache,
        session: URLSession = .shared,
        staleInterval: TimeInterval = 6 * 60 * 60
    ) {
        self.feedURL = feedURL
        self.cache = cache
        self.session = session
        self.staleInterval = staleInterval
    }

    public func cachedFeed() throws -> (feed: CalendarFeed, isStale: Bool) {
        let cached = try cache.load()
        return (cached.feed, Date().timeIntervalSince(cached.modified) >= staleInterval)
    }

    public func refresh() async throws -> CalendarFeed {
        let (data, response) = try await session.data(from: feedURL)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw FeedError.invalidResponse
        }
        return try cache.saveValidated(data)
    }
}
