function closeCurrentWidget(self){
    $(self).parents(".popup").hide();
}

function spawnRecaptcha(id){
    var container = $(id);
    var init = container.attr("hdx-recaptcha");
    if (!init){
      container.attr("hdx-recaptcha", true);
      container.find(".hdx-recaptcha").each(function (idx, el) {
        grecaptcha.render(el);
      });
    }
}

function notYou(){
    $('#field-login').val('');
    $('#field-login').removeClass('input-content');
    $('#username-static, #login-photo-gravatar').hide();
    $('#username-form-field, #login-photo-default').show();
    $('#field-login').focus();
    _displayMfaField();
}

function checkLockout(event) {
  let username = $("#field-login").val();
  let response = $.ajax({
    type: "GET",
    url: `/util/user/check_lockout?user=${username}`,
    cache: false,
    async: false
  }).responseText;
  if (response) {
    let json = JSON.parse(response);
    if (json.result === true){
      _showLoginError(`Too many wrong attempts. Login locked for ${json.timeout} seconds. Please try again later!`);
      event.preventDefault();
    }
  }

}

function showContributorPopup(popupId, pkgTitle, pkgOwnerOrg, pkgId, overwritePopupTitle){
  spawnRecaptcha(popupId);
  //populate popup with hidden fields content
  pkgTitle = decodeURIComponent(pkgTitle);
  let form = $('#contact-contributor-form');
  form.find('input[type="hidden"][name="pkg_title"]').val(pkgTitle);
  form.find('input[type="hidden"][name="pkg_owner_org"]').val(pkgOwnerOrg);
  form.find('input[type="hidden"][name="pkg_id"]').val(pkgId);
  if (overwritePopupTitle) {
    form.find('.contact-popup-title').html(pkgTitle);

  }

  showOnboardingWidget(popupId)
}

function showOnboardingWidget(id, elid, val){
    if (id == "#signupPopup") {
        // we only want to send the analytics event for the sign-up widget
        hdxUtil.analytics.sendUserRegisteredEvent("start user register");
    }
    $(id).show();
    $(id).find("input[type!='button']:visible:first").focus();

    $(id).find('img.gif-auto-play').remove();
    $(id).find('img.gif').each(function(idx, element){
        var el = $(element);
        var src = el.attr("src");
        var clone = el.clone();
        $(el).addClass("hide");
        clone.removeClass("hide");
        clone.attr("src", "");
        clone.addClass("gif-auto-play");
        el.after(clone);
        setTimeout(function(){
            clone.attr("src", src);
        }, 0);
    });
    if(elid){
      $(elid).val(val);
    }
    function _triggerInputDataClass($this){
        if ($this.val() === "")
            $this.removeClass("input-content");
        else
            $this.addClass("input-content");
    }

    $(id).find('input[type="password"], input[type="number"], input[type="text"], textarea').each(
        function(idx, el){
            _triggerInputDataClass($(el));
        }
    );
    $(id).find('input[type="password"], input[type="number"], input[type="text"], textarea').change(
        function(){
            var $this = $(this);
            _triggerInputDataClass($this);
        }
    );
    $(id).find('input[type="password"], input[type="number"], input[type="text"], textarea').on("keyup",
        function(){
            var $this = $(this);
            _triggerInputDataClass($this);
        }
    );

    $(id).find('input[type="submit"]').on("click", function(){
        var result = precheckForm(id);
        return !result;
    });

    function precheckForm(id){
        var error = false;
        $(id).find("input.required, textarea.required, select.required").each(function(idx, el){
            var $el = $(el);
            if ($el.is(":visible") && ($el.val() === null || $el.val() === "")){
                $el.addClass("error");
                error = true;
            } else {
                $el.removeClass("error");
            }
        });
        return error;
    }

    return false;
}

function _showLoginError(loginError) {
  var errMsg = $("#loginPopup").find(".error-message");
  errMsg.text(loginError);
  $("#field-login").addClass("error");
  $("#field-password").addClass("error");
  notYou();
  errMsg.show();
}

function _displayMfaField(show = false) {
  if (show)
    $("#mfa-form-field").show();
  else
    $("#mfa-form-field").hide();
  $("#field-mfa").val("");
}

function checkMfa() {
  console.log("test");
  let username = $("#field-login").val();
  let response = $.ajax({
    type: "GET",
    url: `/util/user/check_mfa?user=${username}`,
    cache: false,
    async: false
  }).responseText;
  if (response) {
    let json = JSON.parse(response);
    if (json.result === true){
      _displayMfaField(true);
      return;
    }
  }
  _displayMfaField();
}


$(document).ready(function(){
    $("#hdx-login-form").submit(checkLockout);
    $("#field-login").change(checkMfa);
    //check cookies
    const loginCookie = $.cookie("hdx_login");
    const loginPopup = $("#loginPopup").length > 0;
    if (loginCookie && loginPopup){
        var data = JSON.parse(loginCookie);
        //console.log(data);

        $('#username-form-field, #login-photo-default').hide();
        $('#field-login').val(data.login);
        $('#user-display-name').text(data.display_name);
        if (data.email)
            $('#user-display-email').text(data.email);
        $('#login-photo-gravatar-img').attr("src", "//gravatar.com/avatar/"+ data.email_hash +"?s=95&d=identicon");
        $('#username-static, #login-photo-gravatar').show();
        checkMfa();
    }

    //check for first login
    var firstLogin = $("#first-login").text();
    if (firstLogin && firstLogin != ""){
        showOnboardingWidget("#registeredPopup");
        return;
    }

    //check for logout event
    var userLogout = $("#user-logout").text();
    if (userLogout && userLogout != ""){
        showOnboardingWidget("#logoutPopup");
        return;
    }
    //check for login error
    var loginError = $("#login-error").text();
    if (loginError && loginError != ""){
      _showLoginError(loginError);
    }

    //check for login info message
    var loginInfo = $("#login-info").text();
    if (loginInfo && loginInfo != ""){
        var errMsg = $("#login-info-message");
        errMsg.text(loginInfo);
        notYou();
        errMsg.show();
    }

    var userLogin = $("#user-login").text();
    if (userLogin && userLogin != ""){
        showOnboardingWidget("#loginPopup");
        return;
    }

    var userRegister = $("#user-register").text();
    if (userRegister && userRegister != ""){
        showOnboardingWidget('#signupPopup');
        return;
    }


});
