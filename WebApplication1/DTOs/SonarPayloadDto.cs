using System.Text.Json.Serialization;

namespace WebApplication1.DTOs
{
    public class SonarPayloadDto
    {
        [JsonPropertyName("slotId")]
        public string SlotId { get; set; } = string.Empty;

        [JsonPropertyName("isOccupied")]
        public bool IsOccupied { get; set; }
    }
}
