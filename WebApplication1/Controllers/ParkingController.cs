using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Caching.Memory;
using WebApplication1.Data;
using WebApplication1.DTOs;
using WebApplication1.Models;
using WebApplication1.Services;

namespace WebApplication1.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class ParkingController : ControllerBase
    {
        private readonly ApplicationDbContext _context;
        private readonly IMemoryCache _cache;
        private readonly GateControlService _gateControlService;
        private const string MapCacheKey = "ParkingMapData";

        public ParkingController(ApplicationDbContext context, IMemoryCache cache, GateControlService gateControlService)
        {
            _context = context;
            _cache = cache;
            _gateControlService = gateControlService;
        }

        // GET api/parking/map
        [HttpGet("map")]
        public async Task<IActionResult> GetMap()
        {
            try
            {
                if (_cache.TryGetValue(MapCacheKey, out List<ParkingSlot>? cachedSlots))
                {
                    return Ok(cachedSlots);
                }

                var slots = await _context.ParkingSlots
                    .AsNoTracking()
                    .OrderBy(s => s.GridY)
                    .ThenBy(s => s.GridX)
                    .ToListAsync();

                var cacheOptions = new MemoryCacheEntryOptions()
                    .SetAbsoluteExpiration(TimeSpan.FromSeconds(5));

                _cache.Set(MapCacheKey, slots, cacheOptions);

                return Ok(slots);
            }
            catch (Exception ex)
            {
                return StatusCode(500, new { message = "Failed to retrieve parking map.", error = ex.Message });
            }
        }

        // POST api/parking/sensor-update
        [HttpPost("sensor-update")]
        public async Task<IActionResult> SensorUpdate([FromBody] SensorUpdateDto updateData)
        {
            try
            {
                var slot = await _context.ParkingSlots.FindAsync(updateData.SlotId);

                if (slot == null)
                {
                    return NotFound(new { message = $"Slot '{updateData.SlotId}' not found." });
                }

                slot.IsOccupied = updateData.IsOccupied;
                await _context.SaveChangesAsync();

                // Invalidate cache so the next poll gets fresh data immediately
                _cache.Remove(MapCacheKey);

                return Ok(new { message = $"Slot '{updateData.SlotId}' updated.", isOccupied = slot.IsOccupied });
            }
            catch (Exception ex)
            {
                return StatusCode(500, new { message = "Failed to update sensor data.", error = ex.Message });
            }
        }

        // POST api/parking/simulate-entry
        [Authorize]
        [HttpPost("simulate-entry")]
        public async Task<IActionResult> SimulateEntry()
        {
            var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
            if (userId == null) return Unauthorized();

            var existingSession = await _context.ParkingSessions
                .AsNoTracking()
                .FirstOrDefaultAsync(s => s.UserId == userId && s.Status == SessionStatus.Active);

            if (existingSession != null)
            {
                return Conflict(new
                {
                    warning = "You already have an active parking session.",
                    licensePlate = existingSession.LicensePlate,
                    entryTime = existingSession.EntryTime
                });
            }

            const int maxParkingSlots = 20;
            var activeSessionsCount = await _context.ParkingSessions
                .CountAsync(s => s.Status == SessionStatus.Active);

            if (activeSessionsCount >= maxParkingSlots)
            {
                return BadRequest(new { message = "Parking lot is full." });
            }

            var slot = await _context.ParkingSlots
                .FirstOrDefaultAsync(s => !s.IsOccupied);

            if (slot == null)
                return BadRequest(new { message = "Parking lot is full." });

            var plate = "MOCK-" + Random.Shared.Next(1000, 9999);

            var session = new ParkingSession
            {
                LicensePlate = plate,
                EntryTime = DateTime.UtcNow,
                Status = SessionStatus.Active,
                UserId = userId
            };

            _context.ParkingSessions.Add(session);
            await _context.SaveChangesAsync();

            return Ok(new { licensePlate = plate, slotId = slot.SlotId });
        }

        // GET api/parking/active-session
        [Authorize]
        [HttpGet("active-session")]
        public async Task<IActionResult> GetActiveSession()
        {
            var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
            if (userId == null) return Unauthorized();

            var session = await _context.ParkingSessions
                .AsNoTracking()
                .FirstOrDefaultAsync(s => s.UserId == userId && s.Status == SessionStatus.Active);

            if (session == null)
                return NotFound(new { message = "No active session." });

            var now = DateTime.UtcNow;
            var duration = now - session.EntryTime;
            var totalHours = duration.TotalHours;
            var currentFee = CalculateDynamicFee(session.EntryTime);

            return Ok(new
            {
                licensePlate = session.LicensePlate,
                entryTime = session.EntryTime,
                currentFee,
                durationHours = Math.Round((decimal)totalHours, 2)
            });
        }

        // POST api/parking/simulate-exit
        [Authorize]
        [HttpPost("simulate-exit")]
        public async Task<IActionResult> SimulateExit()
        {
            var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
            if (userId == null) return Unauthorized();

            using var transaction = await _context.Database.BeginTransactionAsync();
            var isCommitted = false;

            try
            {
                var session = await _context.ParkingSessions
                    .FirstOrDefaultAsync(s => s.UserId == userId && s.Status == SessionStatus.Active);

                if (session == null)
                    return BadRequest(new { message = "No active parking session found." });

                var now = DateTime.UtcNow;
                var exitResult = await ProcessSessionExitAsync(session, userId, now);
                if (!exitResult.Success)
                {
                    var gateNotified = false;
                    string? unpaidGateError = null;

                    try
                    {
                        await _gateControlService.NotifyUnpaidAsync();
                        gateNotified = true;
                    }
                    catch (Exception mqttEx)
                    {
                        unpaidGateError = mqttEx.Message;
                    }

                    return BadRequest(new
                    {
                        message = exitResult.ErrorMessage,
                        gateNotified,
                        gateError = unpaidGateError
                    });
                }

                await _context.SaveChangesAsync();
                await transaction.CommitAsync();
                isCommitted = true;

                var gateOpened = false;
                string? gateError = null;

                try
                {
                    await _gateControlService.OpenGateAsync();
                    gateOpened = true;
                }
                catch (Exception mqttEx)
                {
                    gateError = mqttEx.Message;
                }

                return Ok(new
                {
                    message = "Exit successful.",
                    licensePlate = session.LicensePlate,
                    fee = exitResult.CalculatedFee,
                    durationHours = Math.Round((decimal)exitResult.TotalHours, 2),
                    newBalance = exitResult.NewBalance,
                    gateOpened,
                    gateError
                });
            }
            catch (Exception ex)
            {
                if (!isCommitted)
                {
                    await transaction.RollbackAsync();
                }

                return StatusCode(500, new { message = "Exit failed.", error = ex.Message });
            }
        }

        private async Task<SessionExitResult> ProcessSessionExitAsync(ParkingSession session, string userId, DateTime now)
        {
            var totalHours = (now - session.EntryTime).TotalHours;
            var calculatedFee = CalculateDynamicFee(session.EntryTime);

            var wallet = await _context.Wallets
                .FirstOrDefaultAsync(w => w.UserId == userId);

            if (wallet == null || wallet.Balance < calculatedFee)
            {
                return SessionExitResult.Failed(
                    $"Insufficient balance. The parking fee is {calculatedFee} credits, but your balance is only {wallet?.Balance ?? 0}.");
            }

            wallet.Balance -= calculatedFee;

            var walletTx = new WalletTransaction
            {
                Amount = calculatedFee,
                Type = TransactionType.ParkingFee,
                Status = TransactionStatus.Completed,
                CreatedAt = now,
                WalletId = wallet.Id,
                OrderCode = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
            };
            _context.WalletTransactions.Add(walletTx);

            session.ExitTime = now;
            session.CalculatedFee = calculatedFee;
            session.Status = SessionStatus.Completed;

            return SessionExitResult.Succeeded(calculatedFee, totalHours, wallet.Balance);
        }

        private decimal CalculateDynamicFee(DateTime entryTime)
        {
            var totalHours = (DateTime.UtcNow - entryTime).TotalHours;

            decimal fee = 10_000;

            if (totalHours > 24)
            {
                var overtimeHours = (int)Math.Ceiling(totalHours - 24);
                fee += overtimeHours * 1_000;
            }

            return fee;
        }

        private sealed class SessionExitResult
        {
            public bool Success { get; private init; }
            public string? ErrorMessage { get; private init; }
            public decimal CalculatedFee { get; private init; }
            public double TotalHours { get; private init; }
            public decimal NewBalance { get; private init; }

            public static SessionExitResult Failed(string errorMessage) => new()
            {
                Success = false,
                ErrorMessage = errorMessage
            };

            public static SessionExitResult Succeeded(decimal calculatedFee, double totalHours, decimal newBalance) => new()
            {
                Success = true,
                CalculatedFee = calculatedFee,
                TotalHours = totalHours,
                NewBalance = newBalance
            };
        }
    }
}
