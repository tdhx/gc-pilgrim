import Foundation
import Combine

@MainActor
final class CalendarStore: ObservableObject {
    @Published var feed: CalendarFeed?
    @Published var filters = CalendarFilters()
    @Published var isRefreshing = false
    @Published var isShowingFilters = false
    @Published var errorMessage: String?
    @Published var isUsingStaleCache = false
    @Published var hasFinishedInitialLoad = false

    private let repository: CalendarRepository?

    init(bundle: Bundle = .main, cacheDirectory: URL? = nil) {
        let configured = bundle.object(forInfoDictionaryKey: "CalendarFeedURL") as? String
        guard let configured, let url = URL(string: configured), url.scheme?.hasPrefix("http") == true else {
            repository = nil
            errorMessage = FeedError.missingFeedURL.localizedDescription
            return
        }
        let directory = cacheDirectory ?? FileManager.default.urls(
            for: .cachesDirectory,
            in: .userDomainMask
        )[0]
        repository = CalendarRepository(
            feedURL: url,
            cache: FeedCache(fileURL: directory.appending(path: "SPCPCalendar/calendar-v1.json"))
        )
    }

    var visibleEvents: [CalendarEvent] {
        feed?.events.filter(filters.matches) ?? []
    }

    var filterOptions: FilterOptions {
        FilterOptions(events: feed?.events ?? [])
    }

    func load() async {
        guard !hasFinishedInitialLoad else { return }
        defer { hasFinishedInitialLoad = true }
        guard let repository else { return }

        do {
            let cached = try repository.cachedFeed()
            feed = cached.feed
            isUsingStaleCache = cached.isStale
            if cached.isStale {
                await refresh()
            }
        } catch {
            await refresh()
        }
    }

    func refresh() async {
        guard let repository, !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        do {
            feed = try await repository.refresh()
            errorMessage = nil
            isUsingStaleCache = false
        } catch {
            errorMessage = error.localizedDescription
            isUsingStaleCache = feed != nil
        }
    }

    func resetFilters() {
        filters = CalendarFilters()
    }

    func showAll() {
        filters = CalendarFilters(eventTypes: [])
    }
}
