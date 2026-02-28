using System.ComponentModel.DataAnnotations;

namespace WebApplication1.DTOs
{
    public record SensorUpdateDto
    {
        [Required]
        public string SlotId { get; init; } = null!;

        [Required]
        public bool IsOccupied { get; init; }
    }
}
