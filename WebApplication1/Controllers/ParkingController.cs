using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Caching.Memory;
using WebApplication1.Data;
using WebApplication1.DTOs;
using WebApplication1.Models;

namespace WebApplication1.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class ParkingController : ControllerBase
    {
        private readonly ApplicationDbContext _context;
        private readonly IMemoryCache _cache;
        private const string MapCacheKey = "ParkingMapData";

        public ParkingController(ApplicationDbContext context, IMemoryCache cache)
        {
            _context = context;
            _cache = cache;
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

            var slot = await _context.ParkingSlots
                .FirstOrDefaultAsync(s => !s.IsOccupied);

            if (slot == null)
                return BadRequest(new { message = "Parking lot is full." });

            slot.IsOccupied = true;
            _cache.Remove(MapCacheKey);

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

            decimal currentFee = 10_000;

            if (totalHours > 24)
            {
                var overtimeHours = (int)Math.Ceiling(totalHours - 24);
                currentFee += overtimeHours * 1_000;
            }

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

            try
            {
                var session = await _context.ParkingSessions
                    .FirstOrDefaultAsync(s => s.UserId == userId && s.Status == SessionStatus.Active);

                if (session == null)
                    return BadRequest(new { message = "No active parking session found." });

                // Calculate duration & dynamic fee
                var now = DateTime.UtcNow;
                var duration = now - session.EntryTime;
                var totalHours = duration.TotalHours;

                // Base fee: 10,000 for the first 24 hours
                decimal calculatedFee = 10_000;

                // Overtime: +1,000 per additional hour (partial hours rounded up)
                if (totalHours > 24)
                {
                    var overtimeHours = (int)Math.Ceiling(totalHours - 24);
                    calculatedFee += overtimeHours * 1_000;
                }

                // Check wallet balance
                var wallet = await _context.Wallets
                    .FirstOrDefaultAsync(w => w.UserId == userId);

                if (wallet == null || wallet.Balance < calculatedFee)
                    return BadRequest(new
                    {
                        message = $"Insufficient balance. The parking fee is {calculatedFee} credits, but your balance is only {wallet?.Balance ?? 0}."
                    });

                // Deduct fee
                wallet.Balance -= calculatedFee;

                // Create transaction record
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

                // Close session
                session.ExitTime = now;
                session.CalculatedFee = calculatedFee;
                session.Status = SessionStatus.Completed;

                // Free a slot
                var slot = await _context.ParkingSlots
                    .FirstOrDefaultAsync(s => s.IsOccupied);

                if (slot != null)
                    slot.IsOccupied = false;

                await _context.SaveChangesAsync();
                await transaction.CommitAsync();

                _cache.Remove(MapCacheKey);

                return Ok(new
                {
                    message = "Exit successful.",
                    licensePlate = session.LicensePlate,
                    fee = calculatedFee,
                    durationHours = Math.Round((decimal)totalHours, 2),
                    newBalance = wallet.Balance,
                    slotFreed = slot?.SlotId
                });
            }
            catch (Exception ex)
            {
                await transaction.RollbackAsync();
                return StatusCode(500, new { message = "Exit failed.", error = ex.Message });
            }
        }
    }
}
