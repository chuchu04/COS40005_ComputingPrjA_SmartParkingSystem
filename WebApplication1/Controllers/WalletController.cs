using System.Globalization;
using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using WebApplication1.Data;
using WebApplication1.DTOs;
using WebApplication1.Models;
using WebApplication1.Services;

namespace WebApplication1.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class WalletController : ControllerBase
    {
        private const decimal MinTopUpAmount = 10_000;

        private readonly ApplicationDbContext _context;
        private readonly VnpayService _vnpayService;

        public WalletController(ApplicationDbContext context, VnpayService vnpayService)
        {
            _context = context;
            _vnpayService = vnpayService;
        }

        [Authorize]
        [HttpPost("vnpay/create-payment-url")]
        public async Task<IActionResult> CreateVnpayPaymentUrl([FromBody] CreateTopUpRequestDto dto)
        {
            if (dto.Amount < MinTopUpAmount)
            {
                return BadRequest(new { message = $"Minimum top-up is {MinTopUpAmount.ToString("N0", CultureInfo.InvariantCulture)} VND." });
            }

            var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
            if (userId == null)
            {
                return Unauthorized();
            }

            var wallet = await _context.Wallets.FirstOrDefaultAsync(w => w.UserId == userId);
            if (wallet == null)
            {
                return NotFound(new { message = "Wallet not found." });
            }

            var orderCode = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            while (await _context.WalletTransactions.AnyAsync(t => t.OrderCode == orderCode))
            {
                orderCode++;
            }

            var pendingTx = new WalletTransaction
            {
                WalletId = wallet.Id,
                Amount = Math.Round(dto.Amount, 0, MidpointRounding.AwayFromZero),
                Type = TransactionType.TopUp,
                Status = TransactionStatus.Pending,
                OrderCode = orderCode,
                CreatedAt = DateTime.UtcNow
            };

            _context.WalletTransactions.Add(pendingTx);
            await _context.SaveChangesAsync();

            var paymentUrl = _vnpayService.CreatePaymentUrl(orderCode, pendingTx.Amount, HttpContext.Connection.RemoteIpAddress?.ToString() ?? "127.0.0.1");

            return Ok(new CreateTopUpResponseDto
            {
                OrderCode = orderCode,
                PaymentUrl = paymentUrl
            });
        }

        [AllowAnonymous]
        [HttpGet("vnpay/return")]
        public async Task<IActionResult> HandleVnpayReturn()
        {
            var frontendRedirect = _vnpayService.GetFrontendRedirectUrl();

            if (!_vnpayService.ValidateCallback(Request.Query))
            {
                return Redirect($"{frontendRedirect}?topup=failed&reason=invalid_signature");
            }

            var txnRef = Request.Query["vnp_TxnRef"].ToString();
            var responseCode = Request.Query["vnp_ResponseCode"].ToString();
            var transactionStatus = Request.Query["vnp_TransactionStatus"].ToString();
            var rawAmount = Request.Query["vnp_Amount"].ToString();

            if (!long.TryParse(txnRef, out var orderCode) || !long.TryParse(rawAmount, out var gatewayAmountRaw))
            {
                return Redirect($"{frontendRedirect}?topup=failed&reason=invalid_payload");
            }

            var tx = await _context.WalletTransactions
                .Include(t => t.Wallet)
                .FirstOrDefaultAsync(t => t.OrderCode == orderCode && t.Type == TransactionType.TopUp);

            if (tx == null)
            {
                return Redirect($"{frontendRedirect}?topup=failed&reason=order_not_found");
            }

            var expectedGatewayAmount = (long)Math.Round(tx.Amount * 100, MidpointRounding.AwayFromZero);
            if (expectedGatewayAmount != gatewayAmountRaw)
            {
                tx.Status = TransactionStatus.Failed;
                await _context.SaveChangesAsync();
                return Redirect($"{frontendRedirect}?topup=failed&reason=amount_mismatch");
            }

            if (tx.Status == TransactionStatus.Completed)
            {
                return Redirect($"{frontendRedirect}?topup=success&orderCode={orderCode}");
            }

            if (responseCode == "00" && transactionStatus == "00")
            {
                tx.Status = TransactionStatus.Completed;
                tx.Wallet.Balance += tx.Amount;
                await _context.SaveChangesAsync();
                return Redirect($"{frontendRedirect}?topup=success&orderCode={orderCode}");
            }

            tx.Status = TransactionStatus.Failed;
            await _context.SaveChangesAsync();
            return Redirect($"{frontendRedirect}?topup=failed&reason={responseCode}");
        }

        [Authorize]
        [HttpGet("transactions")]
        public async Task<IActionResult> GetTransactions()
        {
            var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
            if (userId == null)
            {
                return Unauthorized();
            }

            var wallet = await _context.Wallets.FirstOrDefaultAsync(w => w.UserId == userId);
            if (wallet == null)
            {
                return NotFound(new { message = "Wallet not found." });
            }

            var transactions = await _context.WalletTransactions
                .AsNoTracking()
                .Where(t => t.WalletId == wallet.Id)
                .OrderByDescending(t => t.CreatedAt)
                .Select(t => new
                {
                    t.Id,
                    t.Amount,
                    t.Type,
                    t.Status,
                    t.OrderCode,
                    t.CreatedAt
                })
                .ToListAsync();

            return Ok(transactions);
        }
    }
}
