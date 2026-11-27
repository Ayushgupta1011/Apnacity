<form id="reportForm">

    <input id="city" type="text">

    <input id="Area" type="text">

    <textarea id="Issue"></textarea>

    <input
        type="file"
        id="photo"
        accept="image/jpeg,image/png,image/webp"
    >

    <input id="latitude" type="hidden">
    <input id="longitude" type="hidden">

    <p id="locationStatus"></p>
    <p id="submitStatus" class="status-text"></p>

    <div id="result" style="display:none;"></div>

    <button type="submit" id="submitBtn">
        Submit Report
    </button>

</form>

<script src="auth.js"></script>
<script src="report.js"></script>
