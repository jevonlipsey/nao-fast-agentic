// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "stt_worker",
    platforms: [
        .macOS(.v14)
    ],
    dependencies: [
        .package(path: "../FluidAudio")
    ],
    targets: [
        .executableTarget(
            name: "stt_worker",
            dependencies: [
                .product(name: "FluidAudio", package: "FluidAudio")
            ]
        ),
    ]
)
