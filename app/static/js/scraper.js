let inputs = document.getElementsByTagName('textarea'),
    cacheCheckboxes = document.getElementsByClassName('cache'),
    submit = document.getElementById('submit');

function setSubmitEnabled() {
    let completed = true;
    for (let input of inputs) {
        if (!Boolean(input.value.trim())) {
            completed = false;
            break;
        }
    }
    submit.disabled = !completed;
}

function saveInputsToURL() {
    const params = new URLSearchParams();
    for (let input of inputs) {
        params.append(input.name, encodeURIComponent(input.value));
    }
    this.history.pushState({}, '', '?' + params.toString());
}

function loadInputsFromURL() {
    const params = new URLSearchParams(window.location.search);
    for (let input of inputs) {
        const param = params.get(input.name);
        if(param) {
            input.value = decodeURIComponent(params.get(input.name));
        }
    }
}

function getCookieByName(name, cookie)
{
    const found = RegExp(name+"=[^;]+").exec(cookie);
    if(!found) return null;
    return found.toString().replace(/^[^=]+./, "");
}

const parsePeopleSearchSession =
    (directoryCookie) => getCookieByName("_people_search_session", directoryCookie);

document.oninput = function() {
    setSubmitEnabled();
    saveInputsToURL();
}

window.onload = function() {
    loadInputsFromURL();
    setSubmitEnabled();
}

submit.onclick = function() {
    console.log('Trying to start scraper.');
    let payload = {};
    for (let input of inputs) {
        payload[input.name] = input.value.trim();
    }

    payload.people_search_session_cookie = parsePeopleSearchSession(payload.directory_cookie);
    console.log(payload.people_search_session_cookie)
    if(!payload.people_search_session_cookie) {
        alert("Could not find People Search session cookie. Please check your directory cookie and try again.");
        return;
    }

    let caches = {};
    for (let cacheCheckbox of cacheCheckboxes) {
        caches[cacheCheckbox.name] = cacheCheckbox.checked;
    }
    payload.caches = caches;
    fetch('/scraper', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload),
    }).then(response => {
        if (response.ok) {
            submit.textContent = 'Scraper started!';
            submit.classList.add('success');
        } else {
            submit.textContent = 'Scraper run failed.';
            submit.classList.add('fail');
        }
        setTimeout(function() {
            submit.textContent = 'Run Scraper';
            submit.className = '';
        }, 1500);
    });
}
