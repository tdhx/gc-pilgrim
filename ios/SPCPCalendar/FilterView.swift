import SwiftUI

struct FilterView: View {
    @ObservedObject var store: CalendarStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                filterSection("Event type", values: store.filterOptions.eventTypes, selection: $store.filters.eventTypes)
                if store.filters.eventTypes.contains("multicultural") {
                    filterSection(
                        "Multicultural Mass",
                        values: store.filterOptions.multiculturalSubtypes,
                        selection: $store.filters.multiculturalSubtypes
                    )
                }
                filterSection("Church", values: store.filterOptions.churches, selection: $store.filters.churches)
                filterSection("Presider", values: store.filterOptions.presiders, selection: $store.filters.presiders)
            }
            .navigationTitle("Filters")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Reset", action: store.resetFilters)
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    private func filterSection(
        _ title: String,
        values: [String],
        selection: Binding<Set<String>>
    ) -> some View {
        Section(title) {
            ForEach(values, id: \.self) { value in
                Toggle(
                    displayLabel(value),
                    isOn: Binding(
                        get: { selection.wrappedValue.contains(value) },
                        set: { enabled in
                            if enabled {
                                selection.wrappedValue.insert(value)
                            } else {
                                selection.wrappedValue.remove(value)
                            }
                        }
                    )
                )
            }
        }
    }

    private func displayLabel(_ value: String) -> String {
        switch value {
        case "confession": "Reconciliation"
        case "multicultural": "Multicultural Mass"
        default: value.split(separator: " ").map(\.capitalized).joined(separator: " ")
        }
    }
}
