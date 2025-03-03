// Mock data for freshman fall courses
const freshmanFallCourses = {
    "CS 164": [
        { start: "08:00AM", end: "09:00AM", day: "Monday" },
        { start: "10:00AM", end: "11:00AM", day: "Wednesday" },
        { start: "02:00PM", end: "03:00PM", day: "Friday" }
    ],
    "MATH 121": [
        { start: "09:00AM", end: "10:00AM", day: "Tuesday" },
        { start: "11:00AM", end: "12:00PM", day: "Thursday" },
        { start: "01:00PM", end: "02:00PM", day: "Monday" }
    ],
    "ENGL 101": [
        { start: "10:00AM", end: "11:00AM", day: "Monday" },
        { start: "01:00PM", end: "02:00PM", day: "Wednesday" },
        { start: "03:00PM", end: "04:00PM", day: "Friday" }
    ],
    "CHEM 101": [
        { start: "08:00AM", end: "09:00AM", day: "Thursday" },
        { start: "12:00PM", end: "01:00PM", day: "Tuesday" },
        { start: "02:00PM", end: "03:00PM", day: "Wednesday" }
    ],
    "COOP 101": [
        { start: "09:00AM", end: "10:00AM", day: "Friday" },
        { start: "11:00AM", end: "12:00PM", day: "Monday" },
        { start: "03:00PM", end: "04:00PM", day: "Tuesday" }
    ],
    "UNIV 101": [
        { start: "08:00AM", end: "09:00AM", day: "Wednesday" },
        { start: "12:00PM", end: "01:00PM", day: "Friday" },
        { start: "01:00PM", end: "02:00PM", day: "Thursday" }
    ]
};

function timeToMinutes(time) {
    const [hour, min] = time.split(':');
    const isPM = time.includes('PM');
    return (parseInt(hour) % 12 + (isPM ? 12 : 0)) * 60 + parseInt(min.slice(0, 2));
}

function generateSchedule(courses, startTime, endTime, spacing) {
    const startMinutes = timeToMinutes(startTime);
    const endMinutes = timeToMinutes(endTime);
    const gap = spacing === 'spaced-out' ? 60 : (spacing === 'back2back' ? 0 : 30); // Flexible uses 30 min default
    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
    let schedule = [];
    let usedSlots = {};

    courses.forEach(courseCode => {
        const options = freshmanFallCourses[courseCode];
        if (!options) return;

        for (let option of options) {
            const slotStart = timeToMinutes(option.start);
            const slotEnd = timeToMinutes(option.end);
            const day = option.day;

            // Check if slot fits within user preferences and has no conflicts
            if (slotStart >= startMinutes && slotEnd <= endMinutes) {
                if (!usedSlots[day]) usedSlots[day] = [];
                const conflicts = usedSlots[day].some(([s, e]) => 
                    (slotStart < e && slotEnd > s) || 
                    (gap > 0 && (slotStart - e < gap && slotStart > e))
                );

                if (!conflicts) {
                    schedule.push([day, courseCode, `${courseCode} - Freshman Fall`, option.start, option.end]);
                    usedSlots[day].push([slotStart, slotEnd]);
                    break; // Take the first non-conflicting slot
                }
            }
        }
    });

    return schedule.sort((a, b) => days.indexOf(a[0]) - days.indexOf(b[0]) || timeToMinutes(a[3]) - timeToMinutes(b[3]));
}

// Form submission
document.getElementById('scheduleForm')?.addEventListener('submit', function(event) {
    event.preventDefault();
    const courses = [
        document.getElementById('course1').value,
        document.getElementById('course2').value,
        document.getElementById('course3').value,
        document.getElementById('course4').value,
        document.getElementById('course5').value
    ].filter(c => c);
    const startTime = document.getElementById('startTime').value || '8:00AM';
    const endTime = document.getElementById('endTime').value || '5:00PM';
    const spacing = document.getElementById('spacing').value || 'flexible';

    const schedule = generateSchedule(courses, startTime, endTime, spacing);
    localStorage.setItem('schedule', JSON.stringify(schedule));
    window.location.href = 'schedule_result.html';
});

// Display schedule
if (document.getElementById('scheduleContainer')) {
    const schedule = JSON.parse(localStorage.getItem('schedule')) || [];
    const container = document.getElementById('scheduleContainer');
    
    if (schedule.length > 0) {
        container.innerHTML = `
            <div class="schedule-grid">
                <div class="time-column">
                    <div class="time-header">Time</div>
                    ${Array.from({ length: 10 }, (_, i) => `
                        <div class="time-slot">${(i + 8) % 12 || 12}:00${i + 8 < 12 ? 'AM' : 'PM'}</div>
                    `).join('')}
                </div>
                <div class="days-container">
                    ${['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'].map(day => `
                        <div class="day-column">
                            <div class="day-header">${day}</div>
                            <div class="day-slots">
                                ${Array.from({ length: 10 }, (_, i) => `
                                    <div class="slot">
                                        ${schedule.filter(e => e[0] === day).map(event => {
                                            const startMinutes = timeToMinutes(event[3]);
                                            const endMinutes = timeToMinutes(event[4]);
                                            const slotStart = (i + 8) * 60;
                                            if (startMinutes >= slotStart && startMinutes < slotStart + 60) {
                                                return `
                                                    <div class="course-card" style="height:${((endMinutes - startMinutes) / 60 * 60)}px; top:${((startMinutes - slotStart) / 60 * 60)}px;">
                                                        <div class="course-title">${event[1]}</div>
                                                        <div class="course-time">${event[3]} - ${event[4]}</div>
                                                    </div>`;
                                            }
                                            return '';
                                        }).join('')}
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    } else {
        container.innerHTML = '<p class="no-schedule">No schedule generated. Try adjusting your preferences!</p>';
    }
}