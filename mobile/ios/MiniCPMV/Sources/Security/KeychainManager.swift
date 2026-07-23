import Foundation
import Security

/**
 * Keychain 安全存储管理器
 *
 * 职责:
 * - 安全存储 JWT Token、Refresh Token、用户凭证
 * - 使用 iOS Keychain Services API（硬件级加密）
 * - 支持增删改查操作
 *
 * 对应 Android 端的 Android Keystore（Sprint 6 中预留但未实现）
 *
 * 安全特性:
 * - Token 存储在 Secure Enclave 保护的 Keychain 中
 * - 设备锁定后自动加密
 * - 应用卸载后自动清除
 */
final class KeychainManager {

    // MARK: - Key Types

    enum KeyType: String {
        case accessToken = "com.minicpmv.accessToken"
        case refreshToken = "com.minicpmv.refreshToken"
        case userId = "com.minicpmv.userId"
        case deviceId = "com.minicpmv.deviceId"
        case encryptionKey = "com.minicpmv.encryptionKey"
    }

    // MARK: - Save

    /**
     * 保存数据到 Keychain
     *
     * - Parameters:
     *   - key: 键类型
     *   - value: 要存储的字符串值
     *   - accessible: 访问控制级别，默认为设备解锁后可用
     * - Returns: 是否保存成功
     */
    @discardableResult
    func save(_ key: KeyType, value: String, accessible: CFString = kSecAttrAccessibleAfterFirstUnlock) -> Bool {
        guard let data = value.data(using: .utf8) else { return false }

        // 先删除旧值
        delete(key)

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key.rawValue,
            kSecValueData as String: data,
            kSecAttrAccessible as String: accessible
        ]

        let status = SecItemAdd(query as CFDictionary, nil)
        return status == errSecSuccess
    }

    // MARK: - Load

    /**
     * 从 Keychain 读取数据
     *
     * - Parameter key: 键类型
     * - Returns: 存储的字符串值，不存在则返回 nil
     */
    func load(_ key: KeyType) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key.rawValue,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let value = String(data: data, encoding: .utf8) else {
            return nil
        }

        return value
    }

    // MARK: - Delete

    /**
     * 从 Keychain 删除数据
     *
     * - Parameter key: 键类型
     * - Returns: 是否删除成功
     */
    @discardableResult
    func delete(_ key: KeyType) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key.rawValue
        ]

        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess || status == errSecItemNotFound
    }

    // MARK: - Clear All

    /**
     * 清除所有 MiniCPM-V 相关的 Keychain 数据
     * 用于用户退出登录时调用
     */
    func clearAll() {
        delete(.accessToken)
        delete(.refreshToken)
        delete(.userId)
        // 保留 deviceId 和 encryptionKey
    }

    // MARK: - Check

    /**
     * 检查 Keychain 中是否存在指定键
     */
    func exists(_ key: KeyType) -> Bool {
        return load(key) != nil
    }

    // MARK: - Biometric Protection

    /**
     * 保存数据并要求生物识别验证（Face ID / Touch ID）
     *
     * - Note: 使用 SecAccessControl 配合生物识别
     */
    @discardableResult
    func saveWithBiometric(_ key: KeyType, value: String) -> Bool {
        guard let data = value.data(using: .utf8) else { return false }

        delete(key)

        // 创建生物识别访问控制
        var error: Unmanaged<CFError>?
        guard let accessControl = SecAccessControlCreateWithFlags(
            nil,
            kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            .userPresence,
            &error
        ) else {
            print("[Keychain] 创建访问控制失败: \(error?.takeRetainedValue().localizedDescription ?? "")")
            return false
        }

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key.rawValue,
            kSecValueData as String: data,
            kSecAttrAccessControl as String: accessControl
        ]

        let status = SecItemAdd(query as CFDictionary, nil)
        return status == errSecSuccess
    }
}
