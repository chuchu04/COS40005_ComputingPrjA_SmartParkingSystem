using Microsoft.AspNetCore.Identity;

namespace WebApplication1.Models
{
    public class ApplicationUser : IdentityUser
    {
        // Navigation properties
        public Wallet? Wallet { get; set; }
        public ICollection<ParkingSession> ParkingSessions { get; set; } = new List<ParkingSession>();
    }
}
