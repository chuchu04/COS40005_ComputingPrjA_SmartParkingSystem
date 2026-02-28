using System.ComponentModel.DataAnnotations;

namespace WebApplication1.Models
{
    public class ParkingSlot
    {
        [Key]
        public string SlotId { get; set; } = null!; // e.g., "A1", "B2"

        public bool IsOccupied { get; set; } = false;

        public int GridX { get; set; }

        public int GridY { get; set; }
    }
}
