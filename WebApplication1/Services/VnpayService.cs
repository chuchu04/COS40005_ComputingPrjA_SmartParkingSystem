using System.Globalization;
using System.Net;
using System.Security.Cryptography;
using System.Text;

namespace WebApplication1.Services
{
    public sealed class VnpayService
    {
        private readonly IConfiguration _configuration;

        public VnpayService(IConfiguration configuration)
        {
            _configuration = configuration;
        }

        public string CreatePaymentUrl(long orderCode, decimal amount, string clientIp)
        {
            var tmnCode = GetRequiredConfig("Vnpay:TmnCode");
            var hashSecret = GetRequiredConfig("Vnpay:HashSecret");
            var baseUrl = GetRequiredConfig("Vnpay:BaseUrl");
            var returnUrl = GetRequiredConfig("Vnpay:ReturnUrl");

            var version = _configuration["Vnpay:Version"] ?? "2.1.0";
            var command = _configuration["Vnpay:Command"] ?? "pay";
            var currCode = _configuration["Vnpay:CurrCode"] ?? "VND";
            var locale = _configuration["Vnpay:Locale"] ?? "vn";

            var amountForGateway = (long)Math.Round(amount * 100, MidpointRounding.AwayFromZero);
            var createDate = DateTime.UtcNow.AddHours(7).ToString("yyyyMMddHHmmss", CultureInfo.InvariantCulture);

            var request = new SortedDictionary<string, string>(StringComparer.Ordinal)
            {
                ["vnp_Version"] = version,
                ["vnp_Command"] = command,
                ["vnp_TmnCode"] = tmnCode,
                ["vnp_Amount"] = amountForGateway.ToString(CultureInfo.InvariantCulture),
                ["vnp_CreateDate"] = createDate,
                ["vnp_CurrCode"] = currCode,
                ["vnp_IpAddr"] = string.IsNullOrWhiteSpace(clientIp) ? "127.0.0.1" : clientIp,
                ["vnp_Locale"] = locale,
                ["vnp_OrderInfo"] = $"Wallet top-up {orderCode}",
                ["vnp_OrderType"] = "other",
                ["vnp_ReturnUrl"] = returnUrl,
                ["vnp_TxnRef"] = orderCode.ToString(CultureInfo.InvariantCulture)
            };

            var (queryString, signData) = BuildQueryAndSignData(request);
            var secureHash = HmacSha512(hashSecret, signData);
            return $"{baseUrl}?{queryString}&vnp_SecureHash={secureHash}";
        }

        public bool ValidateCallback(IQueryCollection queryCollection)
        {
            var hashSecret = GetRequiredConfig("Vnpay:HashSecret");
            var secureHash = queryCollection["vnp_SecureHash"].ToString();

            if (string.IsNullOrWhiteSpace(secureHash))
            {
                return false;
            }

            var callbackData = new SortedDictionary<string, string>(StringComparer.Ordinal);

            foreach (var kv in queryCollection)
            {
                if (!kv.Key.StartsWith("vnp_", StringComparison.Ordinal))
                {
                    continue;
                }

                if (kv.Key.Equals("vnp_SecureHash", StringComparison.OrdinalIgnoreCase) ||
                    kv.Key.Equals("vnp_SecureHashType", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                var value = kv.Value.ToString();
                if (!string.IsNullOrEmpty(value))
                {
                    callbackData[kv.Key] = value;
                }
            }

            var (_, signData) = BuildQueryAndSignData(callbackData);
            var calculatedHash = HmacSha512(hashSecret, signData);

            return string.Equals(calculatedHash, secureHash, StringComparison.OrdinalIgnoreCase);
        }

        public string GetFrontendRedirectUrl()
        {
            return GetRequiredConfig("Vnpay:FrontendRedirectUrl");
        }

        private static (string queryString, string signData) BuildQueryAndSignData(SortedDictionary<string, string> data)
        {
            var queryParts = data
                .Where(kv => !string.IsNullOrWhiteSpace(kv.Value))
                .Select(kv => $"{WebUtility.UrlEncode(kv.Key)}={WebUtility.UrlEncode(kv.Value)}")
                .ToList();

            var queryString = string.Join("&", queryParts);
            return (queryString, queryString);
        }

        private static string HmacSha512(string key, string inputData)
        {
            var keyBytes = Encoding.UTF8.GetBytes(key);
            var inputBytes = Encoding.UTF8.GetBytes(inputData);
            using var hmac = new HMACSHA512(keyBytes);
            var hashValue = hmac.ComputeHash(inputBytes);

            var sb = new StringBuilder(hashValue.Length * 2);
            foreach (var b in hashValue)
            {
                sb.Append(b.ToString("x2", CultureInfo.InvariantCulture));
            }

            return sb.ToString();
        }

        private string GetRequiredConfig(string key)
        {
            var value = _configuration[key];
            if (string.IsNullOrWhiteSpace(value))
            {
                throw new InvalidOperationException($"Missing required configuration: {key}");
            }

            return value;
        }
    }
}
