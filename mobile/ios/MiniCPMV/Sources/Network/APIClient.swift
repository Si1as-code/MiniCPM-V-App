import Foundation

/**
 * 网络层 API 客户端
 *
 * 职责:
 * - 封装 URLSession HTTP 请求
 * - 自动注入 JWT Token（从 Keychain 读取）
 * - 对接 Sprint 4 FastAPI 后端
 * - JSON 序列化/反序列化
 *
 * 对应 Android 端的 RetrofitClient + ApiService
 */
final class APIClient {

    // MARK: - Properties

    private let baseURL: URL
    private let session: URLSession
    private let keychain: KeychainManager
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    // MARK: - Initialization

    init(keychain: KeychainManager, baseURL: URL = URL(string: "https://api.minicpmv.example.com")!) {
        self.keychain = keychain
        self.baseURL = baseURL

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        config.waitsForConnectivity = true
        self.session = URLSession(configuration: config)

        self.decoder = JSONDecoder()
        self.decoder.dateDecodingStrategy = .iso8601

        self.encoder = JSONEncoder()
        self.encoder.dateEncodingStrategy = .iso8601
    }

    // MARK: - HTTP Methods

    /**
     * GET 请求
     */
    func get<T: Decodable>(_ endpoint: String, queryItems: [URLQueryItem] = []) async throws -> T {
        let request = try buildRequest(endpoint: endpoint, method: "GET", queryItems: queryItems)
        return try await execute(request)
    }

    /**
     * POST 请求
     */
    func post<T: Decodable, B: Encodable>(_ endpoint: String, body: B) async throws -> T {
        let bodyData = try encoder.encode(body)
        let request = try buildRequest(endpoint: endpoint, method: "POST", body: bodyData)
        return try await execute(request)
    }

    /**
     * POST 请求（无响应体）
     */
    func post<B: Encodable>(_ endpoint: String, body: B) async throws {
        let bodyData = try encoder.encode(body)
        let request = try buildRequest(endpoint: endpoint, method: "POST", body: bodyData)
        let (_, response) = try await session.data(for: request)
        try validateResponse(response)
    }

    // MARK: - Request Building

    private func buildRequest(
        endpoint: String,
        method: String,
        body: Data? = nil,
        queryItems: [URLQueryItem] = []
    ) throws -> URLRequest {
        var components = URLComponents(url: baseURL.appendingPathComponent(endpoint), resolvingAgainstBaseURL: false)
        if !queryItems.isEmpty {
            components?.queryItems = queryItems
        }

        guard let url = components?.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        // 注入 JWT Token
        if let token = keychain.load(.accessToken) {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let body = body {
            request.httpBody = body
        }

        return request
    }

    // MARK: - Execution

    private func execute<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: request)
        try validateResponse(response)

        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingError(error.localizedDescription)
        }
    }

    private func validateResponse(_ response: URLResponse) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        switch httpResponse.statusCode {
        case 200...299:
            return
        case 401:
            throw APIError.unauthorized
        case 403:
            throw APIError.forbidden
        case 429:
            throw APIError.rateLimited
        case 500...599:
            throw APIError.serverError(httpResponse.statusCode)
        default:
            throw APIError.unknown(httpResponse.statusCode)
        }
    }
}

// MARK: - API Errors

enum APIError: LocalizedError {
    case invalidURL
    case invalidResponse
    case unauthorized
    case forbidden
    case rateLimited
    case serverError(Int)
    case unknown(Int)
    case decodingError(String)

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "无效的 URL"
        case .invalidResponse: return "无效的响应"
        case .unauthorized: return "未授权，请重新登录"
        case .forbidden: return "禁止访问"
        case .rateLimited: return "请求过于频繁，请稍后再试"
        case .serverError(let code): return "服务器错误 (\(code))"
        case .unknown(let code): return "未知错误 (\(code))"
        case .decodingError(let msg): return "数据解析失败: \(msg)"
        }
    }
}

// MARK: - API Models

struct InferenceRequest: Encodable {
    let imageBase64: String
    let question: String
    let modelVersion: String
    let forceLocal: Bool

    enum CodingKeys: String, CodingKey {
        case imageBase64 = "image_base64"
        case question
        case modelVersion = "model_version"
        case forceLocal = "force_local"
    }
}

struct InferenceResponse: Decodable {
    let answer: String
    let confidence: Float
    let modelVersion: String
    let latencyMs: Int
    let taskType: String

    enum CodingKeys: String, CodingKey {
        case answer, confidence
        case modelVersion = "model_version"
        case latencyMs = "latency_ms"
        case taskType = "task_type"
    }
}

struct SyncResponse: Decodable {
    let uploaded: Int
    let conflicts: Int
    let message: String
}

struct StatsResponse: Decodable {
    let totalInferences: Int
    let localInferences: Int
    let cloudInferences: Int
    let avgConfidence: Float
    let totalCost: Float

    enum CodingKeys: String, CodingKey {
        case totalInferences = "total_inferences"
        case localInferences = "local_inferences"
        case cloudInferences = "cloud_inferences"
        case avgConfidence = "avg_confidence"
        case totalCost = "total_cost"
    }
}
