import SwiftUI

@main
struct SPCPCalendarApp: App {
    @StateObject private var store = CalendarStore()

    var body: some Scene {
        WindowGroup {
            CalendarView(store: store)
        }
    }
}
