/* script.js */
document.getElementById("edit-btn").addEventListener("click", function() {
    document.querySelector(".profile-details").style.display = "none";
    document.querySelector(".profile-edit-form").style.display = "block";
});

document.getElementById("cancel-edit").addEventListener("click", function() {
    document.querySelector(".profile-details").style.display = "block";
    document.querySelector(".profile-edit-form").style.display = "none";
});

document.getElementById("profile-form").addEventListener("submit", function(event) {
    event.preventDefault();
    document.getElementById("display-name").innerText = document.getElementById("name").value;
    document.getElementById("display-email").innerText = document.getElementById("email").value;
    document.getElementById("display-major").innerText = document.getElementById("major").value;
    document.getElementById("display-minor").innerText = document.getElementById("minor").value;
    document.getElementById("display-year").innerText = document.getElementById("year").value;
    document.getElementById("display-coop-year").innerText = document.getElementById("coop-year").value;
    document.getElementById("display-cycle").innerText = document.getElementById("cycle").value;
    document.querySelector(".profile-details").style.display = "block";
    document.querySelector(".profile-edit-form").style.display = "none";
});

document.getElementById("upload-pic").addEventListener("change", function(event) {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            document.getElementById("profile-pic").src = e.target.result;
        };
        reader.readAsDataURL(file);
    }
});
