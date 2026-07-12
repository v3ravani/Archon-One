document.addEventListener("DOMContentLoaded", () => {
    // 1. Sidebar Active Link Highlighting on Scroll
    const navLinks = document.querySelectorAll(".sidebar-nav a");
    const sections = document.querySelectorAll("section.doc-section");

    function highlightNav() {
        let scrollY = window.scrollY || window.pageYOffset;
        const headerOffset = 100;
        let currentSectionId = "";
        
        sections.forEach(section => {
            const sectionTop = section.offsetTop - headerOffset;
            const sectionHeight = section.offsetHeight;
            
            if (scrollY >= sectionTop && scrollY < sectionTop + sectionHeight) {
                currentSectionId = section.getAttribute("id");
            }
        });
        
        if (currentSectionId) {
            navLinks.forEach(link => {
                link.classList.remove("active");
                if (link.getAttribute("href") === `#${currentSectionId}`) {
                    link.classList.add("active");
                }
            });
        }
    }
    
    window.addEventListener("scroll", highlightNav);
    highlightNav();

    // 2. Mobile Menu Toggle
    const menuToggle = document.getElementById("menu-toggle");
    const sidebar = document.querySelector(".sidebar");
    
    if (menuToggle && sidebar) {
        menuToggle.addEventListener("click", () => {
            sidebar.classList.toggle("open");
            // Toggle hamburger icon between menu representation and cross representation
            if (sidebar.classList.contains("open")) {
                menuToggle.textContent = "✕";
            } else {
                menuToggle.textContent = "☰";
            }
        });
        
        // Hide sidebar when clicking a link inside it on mobile
        const sidebarLinks = sidebar.querySelectorAll(".sidebar-nav a");
        sidebarLinks.forEach(link => {
            link.addEventListener("click", () => {
                sidebar.classList.remove("open");
                menuToggle.textContent = "☰";
            });
        });
    }

    // 3. Search Documentation Filter (Desktop & Mobile synchronized)
    const searchInput = document.getElementById("search-input");
    const mobileSearchInput = document.getElementById("mobile-search-input");
    
    function performSearch(query) {
        sections.forEach(section => {
            const textContent = section.textContent.toLowerCase();
            
            if (query === "") {
                section.classList.remove("search-hidden");
                section.querySelectorAll(".doc-sub-item").forEach(item => {
                    item.classList.remove("search-hidden");
                });
            } else {
                const sectionTitle = section.querySelector("h2") ? section.querySelector("h2").textContent.toLowerCase() : "";
                let hasMatch = textContent.includes(query);
                
                if (hasMatch) {
                    section.classList.remove("search-hidden");
                    let subMatches = 0;
                    const subItems = section.querySelectorAll(".doc-sub-item");
                    
                    if (subItems.length > 0) {
                        subItems.forEach(item => {
                            const itemText = item.textContent.toLowerCase();
                            if (itemText.includes(query)) {
                                item.classList.remove("search-hidden");
                                subMatches++;
                            } else {
                                item.classList.add("search-hidden");
                            }
                        });
                        
                        if (subMatches === 0 && sectionTitle.includes(query)) {
                            subItems.forEach(item => item.classList.remove("search-hidden"));
                        }
                    }
                } else {
                    section.classList.add("search-hidden");
                }
            }
        });
        highlightNav();
    }

    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            const query = e.target.value.toLowerCase().trim();
            if (mobileSearchInput) mobileSearchInput.value = e.target.value;
            performSearch(query);
        });
    }

    if (mobileSearchInput) {
        mobileSearchInput.addEventListener("input", (e) => {
            const query = e.target.value.toLowerCase().trim();
            if (searchInput) searchInput.value = e.target.value;
            performSearch(query);
        });
    }
});
