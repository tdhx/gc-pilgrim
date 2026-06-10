// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "SPCPCalendarCore",
    platforms: [.iOS(.v17), .macOS(.v13)],
    products: [
        .library(name: "SPCPCalendarCore", targets: ["SPCPCalendarCore"])
    ],
    targets: [
        .target(name: "SPCPCalendarCore"),
        .testTarget(
            name: "SPCPCalendarCoreTests",
            dependencies: ["SPCPCalendarCore"],
            resources: [.copy("Fixtures")]
        )
    ]
)
