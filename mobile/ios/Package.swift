// swift-tools-version: 5.9
// MiniCPM-V iOS - Swift Package Manager
import PackageDescription

let package = Package(
    name: "MiniCPMV",
    platforms: [
        .iOS(.v17)
    ],
    products: [
        .executable(name: "MiniCPMV", targets: ["MiniCPMV"]),
        .library(name: "MiniCPMVWidget", targets: ["MiniCPMVWidget"]),
    ],
    dependencies: [
        // Core ML 推理（系统框架，无需第三方依赖）
        // Keychain（系统框架）
        // BGTaskScheduler（系统框架）
    ],
    targets: [
        .executableTarget(
            name: "MiniCPMV",
            path: "MiniCPMV/Sources"
        ),
        .target(
            name: "MiniCPMVWidget",
            path: "Widget/Sources",
            dependencies: ["MiniCPMV"]
        ),
        .testTarget(
            name: "MiniCPMVTests",
            dependencies: ["MiniCPMV"],
            path: "MiniCPMV/Tests"
        ),
    ]
)
