using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace WebApplication1.Models
{
    public class ParkingSession
    {
        [Key]
        public Guid Id { get; set; } = Guid.NewGuid();

        [Required]
        [MaxLength(20)]
        public string LicensePlate { get; set; } = null!;

        public DateTime EntryTime { get; set; } = DateTime.UtcNow;

        public DateTime? ExitTime { get; set; }

        [Column(TypeName = "decimal(18,2)")]
        public decimal? CalculatedFee { get; set; }

        [Column(TypeName = "decimal(18,2)")]
        public decimal DiscountAmount { get; set; } = 0;

        public SessionStatus Status { get; set; } = SessionStatus.Active;

        // Foreign key to ApplicationUser
        [Required]
        public string UserId { get; set; } = null!;

        [ForeignKey("UserId")]
        public ApplicationUser User { get; set; } = null!;

        // Foreign key to RetailReceipt (optional)
        [MaxLength(50)]
        public string? AppliedReceiptUid { get; set; }

        [ForeignKey("AppliedReceiptUid")]
        public RetailReceipt? AppliedReceipt { get; set; }
    }
}
