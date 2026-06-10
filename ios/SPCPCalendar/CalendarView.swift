import SwiftUI

struct CalendarView: View {
    @ObservedObject var store: CalendarStore

    var body: some View {
        NavigationStack {
            Group {
                if let feed = store.feed {
                    eventList(feed: feed)
                } else if store.hasFinishedInitialLoad {
                    ContentUnavailableView(
                        "Calendar unavailable",
                        systemImage: "calendar.badge.exclamationmark",
                        description: Text(store.errorMessage ?? "No cached calendar is available.")
                    )
                } else {
                    ProgressView("Loading calendar")
                }
            }
            .navigationTitle("SPCP Calendar")
            .searchable(text: $store.filters.search, prompt: "Event, church or presider")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Show all", action: store.showAll)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        store.isShowingFilters = true
                    } label: {
                        Label("Filters", systemImage: "line.3.horizontal.decrease.circle")
                    }
                }
            }
            .sheet(isPresented: $store.isShowingFilters) {
                FilterView(store: store)
            }
            .task { await store.load() }
        }
    }

    @ViewBuilder
    private func eventList(feed: CalendarFeed) -> some View {
        List {
            if store.isUsingStaleCache || store.errorMessage != nil {
                Section {
                    Label(
                        store.isUsingStaleCache
                            ? "Showing the last downloaded calendar."
                            : (store.errorMessage ?? "Calendar refresh failed."),
                        systemImage: "wifi.exclamationmark"
                    )
                    .foregroundStyle(.orange)
                    if let error = store.errorMessage {
                        Text(error).font(.caption).foregroundStyle(.secondary)
                    }
                }
            }

            Section {
                if store.visibleEvents.isEmpty {
                    ContentUnavailableView.search(text: store.filters.search)
                } else {
                    ForEach(store.visibleEvents) { event in
                        EventRow(event: event)
                    }
                }
            } header: {
                Text("\(store.visibleEvents.count) events")
            } footer: {
                Text(
                    "Generated \(feed.generatedAt.formatted(date: .abbreviated, time: .shortened)) · "
                    + "\(feed.coverage.start) to \(feed.coverage.end)"
                )
            }
        }
        .refreshable { await store.refresh() }
        .overlay {
            if store.isRefreshing && store.feed == nil {
                ProgressView()
            }
        }
    }
}

private struct EventRow: View {
    let event: CalendarEvent

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            VStack(spacing: 1) {
                Text(startDate.formatted(.dateTime.weekday(.abbreviated)))
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(.secondary)
                Text(startDate.formatted(.dateTime.day()))
                    .font(.title2.weight(.semibold))
                Text(startDate.formatted(.dateTime.month(.abbreviated)))
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .frame(width: 42)

            VStack(alignment: .leading, spacing: 5) {
                HStack {
                    Text(timeText)
                    Text(event.serviceName)
                }
                .font(.caption.weight(.semibold))
                .foregroundStyle(Color.accentColor)

                Text(event.displayTitle)
                    .font(.headline)

                tagLine("Church", event.displayChurch)
                tagLine("Presider", event.presiders.isEmpty ? "TBA" : event.presiders.joined(separator: ", "))
                if event.isVigil {
                    Text("Vigil").font(.caption).foregroundStyle(.secondary)
                } else if let rank = event.liturgical?.rank {
                    Text(rank).font(.caption).foregroundStyle(.secondary)
                }
                if let season = event.liturgical?.season {
                    Text(season).font(.caption).foregroundStyle(.secondary)
                }
            }
        }
        .padding(.vertical, 5)
    }

    private var startDate: Date {
        event.allDay
            ? CalendarEventFormatters.dateOnly.date(from: event.start) ?? .distantPast
            : CalendarEventFormatters.iso.date(from: event.start) ?? .distantPast
    }

    private var endDate: Date {
        event.allDay
            ? CalendarEventFormatters.dateOnly.date(from: event.end) ?? .distantPast
            : CalendarEventFormatters.iso.date(from: event.end) ?? .distantPast
    }

    private var timeText: String {
        event.allDay
            ? "All day"
            : "\(startDate.formatted(date: .omitted, time: .shortened))–\(endDate.formatted(date: .omitted, time: .shortened))"
    }

    private func tagLine(_ label: String, _ value: String) -> some View {
        Text("\(label): \(value)")
            .font(.caption)
            .foregroundStyle(.secondary)
    }
}

@MainActor
private enum CalendarEventFormatters {
    static let iso = ISO8601DateFormatter()
    static let dateOnly: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_AU")
        formatter.timeZone = TimeZone(identifier: "Australia/Brisbane")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()
}
