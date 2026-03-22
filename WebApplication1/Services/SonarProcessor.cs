using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging;
using WebApplication1.Data;
using WebApplication1.DTOs;

namespace WebApplication1.Services
{
    public class SonarProcessor
    {
        private readonly IServiceScopeFactory _scopeFactory;
        private readonly ILogger<SonarProcessor> _logger;
        private const string MapCacheKey = "ParkingMapData";

        public SonarProcessor(IServiceScopeFactory scopeFactory, ILogger<SonarProcessor> logger)
        {
            _scopeFactory = scopeFactory;
            _logger = logger;
        }

        public async Task ProcessUpdateAsync(string payloadJson)
        {
            if (string.IsNullOrWhiteSpace(payloadJson))
            {
                _logger.LogWarning("Sonar payload was empty. Skipping update.");
                return;
            }

            var payload = JsonSerializer.Deserialize<SonarPayloadDto>(
                payloadJson,
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });

            if (payload == null || string.IsNullOrWhiteSpace(payload.SlotId))
            {
                _logger.LogWarning("Invalid sonar payload JSON: {Payload}", payloadJson);
                return;
            }

            _logger.LogInformation("Processing sonar update. SlotId={SlotId}, IsOccupied={IsOccupied}", payload.SlotId, payload.IsOccupied);

            using var scope = _scopeFactory.CreateScope();
            var dbContext = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            var cache = scope.ServiceProvider.GetRequiredService<IMemoryCache>();

            var slot = await dbContext.ParkingSlots
                .FirstOrDefaultAsync(s => s.SlotId == payload.SlotId);

            if (slot == null)
            {
                _logger.LogWarning("Sonar payload referenced unknown slot {SlotId}", payload.SlotId);
                return;
            }

            slot.IsOccupied = payload.IsOccupied;
            await dbContext.SaveChangesAsync();

            cache.Remove(MapCacheKey);
            _logger.LogInformation("Updated slot {SlotId} occupancy to {IsOccupied} and invalidated cache key {CacheKey}", payload.SlotId, payload.IsOccupied, MapCacheKey);
        }
    }
}
