function openTab(evt, tabName) {
  var i, tabcontent, tablinks;
  tabcontent = document.getElementsByClassName("tabcontent");
  for (i = 0; i < tabcontent.length; i++) {
    tabcontent[i].style.display = "none";
  }
  tablinks = document.getElementsByClassName("tablinks");
  for (i = 0; i < tablinks.length; i++) {
    tablinks[i].className = tablinks[i].className.replace(" active", "");
  }
  document.getElementById(tabName).style.display = "block";
  evt.currentTarget.className += " active";
}

document
  .getElementById("businessDataForm")
  .addEventListener("submit", async function (e) {
    e.preventDefault();

    // Collect form data
    const formData = {
      company_name: document.getElementById("company_name").value,
      tagline: document.getElementById("tagline").value,
      website_url: document.getElementById("website_url").value,
      email: document.getElementById("email").value,
      phone: document.getElementById("phone").value,
      business_description: document.getElementById("business_description")
        .value,
      social_media_links: {
        facebook: document.getElementById("facebook").value,
        twitter: document.getElementById("twitter").value,
        linkedin: document.getElementById("linkedin").value,
        instagram: document.getElementById("instagram").value,
      },
      founder_name: document.getElementById("founder_name").value,
      business_category: document.getElementById("business_category").value,
      keywords: document
        .getElementById("keywords")
        .value.split(",")
        .map((k) => k.trim()),
      address: document.getElementById("address").value,
      location: {
        city: document.getElementById("city").value,
        state: document.getElementById("state").value,
        country: document.getElementById("country").value,
        zip: document.getElementById("zip").value,
      },
    };

    try {
      const response = await fetch("/submit-business-data", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      });

      const data = await response.json();

      if (data.status === "success") {
        alert(
          "Business information saved successfully! Business ID: " +
            data.business_id
        );

        // Show CSV upload section
        document.getElementById("business_id").value = data.business_id;
        document.getElementById("csvUploadSection").classList.remove("hidden");
      }
    } catch (error) {
      console.error("Error:", error);
      alert("An error occurred. Please try again.");
    }
  });

document
  .getElementById("csvUploadForm")
  .addEventListener("submit", async function (e) {
    e.preventDefault();

    const formData = new FormData();
    formData.append("file", document.getElementById("csvFile").files[0]);
    formData.append(
      "business_id",
      document.getElementById("business_id").value
    );

    try {
      const response = await fetch("/upload-csv", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (data.status === "success") {
        alert("CSV uploaded and processing started! " + data.message);

        // Switch to status tab
        document.getElementById("check_business_id").value =
          document.getElementById("business_id").value;
        const statusTabButton = document.querySelector(
          "button.tablinks:nth-child(2)"
        );
        statusTabButton.click();

        // Trigger status check
        document
          .getElementById("statusCheckForm")
          .dispatchEvent(new Event("submit"));
      }
    } catch (error) {
      console.error("Error:", error);
      alert("An error occurred. Please try again.");
    }
  });

document
  .getElementById("statusCheckForm")
  .addEventListener("submit", async function (e) {
    e.preventDefault();

    const businessId = document.getElementById("check_business_id").value;

    try {
      const response = await fetch(`/status/${businessId}`);
      const data = await response.json();

      // Show results section
      document.getElementById("statusResults").classList.remove("hidden");

      // Show buttons if there are results
      if (data.statuses && data.statuses.length > 0) {
        document.getElementById("refreshStatus").classList.remove("hidden");
        document.getElementById("checkListings").classList.remove("hidden");
      }

      // Display results
      const statusList = document.getElementById("statusList");
      statusList.innerHTML = "";

      if (data.statuses && data.statuses.length > 0) {
        data.statuses.forEach((status) => {
          const statusClass =
            status.status === "success"
              ? "status-success"
              : status.status === "pending"
              ? "status-pending"
              : "status-error";

          let listingStatus = "";
          if (status.listing_status === "live") {
            listingStatus =
              '<strong>Listing Status:</strong> <span style="color: green;">Live</span><br>';
          } else if (status.listing_status === "potential") {
            listingStatus =
              '<strong>Listing Status:</strong> <span style="color: orange;">Potentially Live</span><br>';
          } else {
            listingStatus =
              '<strong>Listing Status:</strong> <span style="color: red;">Not Found</span><br>';
          }

          const lastChecked = status.last_checked
            ? `<strong>Last Checked:</strong> ${new Date(
                status.last_checked
              ).toLocaleString()}<br>`
            : "";

          statusList.innerHTML += `
                            <div class="status-item ${statusClass}">
                                <strong>URL:</strong> ${
                                  status.directory_url
                                }<br>
                                <strong>Status:</strong> ${status.status}<br>
                                ${listingStatus}
                                ${lastChecked}
                                <strong>Submitted:</strong> ${new Date(
                                  status.created_at
                                ).toLocaleString()}<br>
                                ${
                                  status.updated_at
                                    ? `<strong>Updated:</strong> ${new Date(
                                        status.updated_at
                                      ).toLocaleString()}<br>`
                                    : ""
                                }
                            </div>
                        `;
        });
      } else {
        statusList.innerHTML =
          "<p>No submissions found for this business ID.</p>";
      }
    } catch (error) {
      console.error("Error:", error);
      alert("An error occurred. Please try again.");
    }
  });

document.getElementById("refreshStatus").addEventListener("click", function () {
  document.getElementById("statusCheckForm").dispatchEvent(new Event("submit"));
});

document
  .getElementById("checkListings")
  .addEventListener("click", async function () {
    const businessId = document.getElementById("check_business_id").value;

    try {
      const response = await fetch(`/check-listings/${businessId}`, {
        method: "POST",
      });

      const data = await response.json();

      if (data.status === "success") {
        alert("Listing check triggered! This may take a few minutes.");

        // Reload status after a delay to give time for checking
        setTimeout(() => {
          document
            .getElementById("statusCheckForm")
            .dispatchEvent(new Event("submit"));
        }, 10000);
      }
    } catch (error) {
      console.error("Error:", error);
      alert("An error occurred. Please try again.");
    }
  });
