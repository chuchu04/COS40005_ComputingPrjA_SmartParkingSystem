using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace WebApplication1.Models
{
    public class RetailReceipt
    {
        [Key]
        [MaxLength(50)]
        public string ReceiptUid { get; set; } = null!;

        [Column(TypeName = "decimal(18,2)")]
        public decimal PurchaseAmount { get; set; }

        public bool IsClaimed { get; set; } = false;

        // Navigation property
        public ICollection<ParkingSession> ParkingSessions { get; set; } = new List<ParkingSession>();
    }
}
