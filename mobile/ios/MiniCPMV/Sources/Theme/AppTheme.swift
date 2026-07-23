import SwiftUI

/**
 * MiniCPM-V iOS 应用主题
 *
 * 配色与 Android 端保持一致
 */
enum AppTheme {
    // 主色调
    static let primaryBlue = Color(red: 0.145, green: 0.388, blue: 0.922)    // #2563EB
    static let primaryLight = Color(red: 0.231, green: 0.510, blue: 0.965)  // #3B82F6
    static let primaryDark = Color(red: 0.114, green: 0.306, blue: 0.847)   // #1D4ED8

    // 辅助色
    static let secondaryTeal = Color(red: 0.051, green: 0.580, blue: 0.533) // #0D9488
    static let successGreen = Color(red: 0.063, green: 0.722, blue: 0.506)  // #10B981
    static let warningAmber = Color(red: 0.961, green: 0.620, blue: 0.043)  // #F59E0B
    static let errorRed = Color(red: 0.937, green: 0.267, blue: 0.267)      // #EF4444

    // 背景
    static let background = Color(red: 0.973, green: 0.980, blue: 0.988)    // #F8FAFC
    static let surface = Color.white
    static let surfaceVariant = Color(red: 0.945, green: 0.961, blue: 0.976) // #F1F5F9

    // 文字
    static let primaryText = Color(red: 0.059, green: 0.090, blue: 0.165)   // #0F172A
    static let secondaryText = Color(red: 0.392, green: 0.451, blue: 0.533) // #64748B

    // 分割线
    static let divider = Color(red: 0.886, green: 0.910, blue: 0.941)       // #E2E8F0

    // 尺寸
    static let cornerRadius: CGFloat = 12
    static let cardPadding: CGFloat = 16
    static let sectionSpacing: CGFloat = 16
}

/**
 * 自定义字体排版
 */
enum AppTypography {
    static let largeTitle = Font.system(size: 32, weight: .bold, design: .default)
    static let title = Font.system(size: 24, weight: .semibold, design: .default)
    static let title2 = Font.system(size: 20, weight: .semibold, design: .default)
    static let headline = Font.system(size: 17, weight: .semibold, design: .default)
    static let body = Font.system(size: 16, weight: .regular, design: .default)
    static let callout = Font.system(size: 15, weight: .regular, design: .default)
    static let subheadline = Font.system(size: 14, weight: .regular, design: .default)
    static let footnote = Font.system(size: 13, weight: .regular, design: .default)
    static let caption = Font.system(size: 12, weight: .regular, design: .default)
    static let captionBold = Font.system(size: 12, weight: .semibold, design: .default)
}
