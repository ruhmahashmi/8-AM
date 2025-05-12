document.addEventListener('DOMContentLoaded', function() {
    const tableWrapper = document.querySelector('.table-wrapper');
    const leftArrow = document.querySelector('.arrow.left');
    const rightArrow = document.querySelector('.arrow.right');

    if (tableWrapper && leftArrow && rightArrow) {
        const scrollAmount = 200; // Pixels to scroll per click

        leftArrow.addEventListener('click', () => {
            tableWrapper.scrollBy({ left: -scrollAmount, behavior: 'smooth' });
        });

        rightArrow.addEventListener('click', () => {
            tableWrapper.scrollBy({ left: scrollAmount, behavior: 'smooth' });
        });

        // Show/hide arrows based on scroll position
        tableWrapper.addEventListener('scroll', () => {
            const maxScrollLeft = tableWrapper.scrollWidth - tableWrapper.clientWidth;
            leftArrow.style.display = tableWrapper.scrollLeft > 0 ? 'block' : 'none';
            rightArrow.style.display = tableWrapper.scrollLeft < maxScrollLeft ? 'block' : 'none';
        });

        // Initial check for arrow visibility
        const maxScrollLeft = tableWrapper.scrollWidth - tableWrapper.clientWidth;
        leftArrow.style.display = tableWrapper.scrollLeft > 0 ? 'block' : 'none';
        rightArrow.style.display = maxScrollLeft > 0 ? 'block' : 'none';
    }
});