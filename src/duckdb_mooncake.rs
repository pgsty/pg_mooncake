use crate::utils::DATABASE;
use pgrx::{pg_guard, pg_sys};
use std::ffi::{c_char, c_void, CString};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::OnceLock;

static ATTACH: OnceLock<CString> = OnceLock::new();
static READ_AFTER_COMMIT: AtomicBool = AtomicBool::new(false);

pub(crate) fn init() {
    unsafe { pg_sys::RegisterXactCallback(Some(after_commit), std::ptr::null_mut()) };
}

pub(crate) fn prepare_attach() {
    if ATTACH.get().is_none()
        && unsafe { pg_sys::MyDatabaseId != pg_sys::InvalidOid && pg_sys::IsTransactionState() }
    {
        ATTACH.get_or_init(|| {
            let database = DATABASE.replace('\'', "''");
            let socket = crate::data_directory::socket_path().replace('\'', "''");
            CString::new(format!(
                "ATTACH DATABASE 'mooncake' (TYPE mooncake, URI '{socket}', DATABASE '{database}')"
            ))
            .unwrap()
        });
    }
}

#[pg_guard]
unsafe extern "C-unwind" fn after_commit(event: pg_sys::XactEvent::Type, _arg: *mut c_void) {
    if event == pg_sys::XactEvent::XACT_EVENT_COMMIT && pg_sys::XactLastCommitEnd != 0 {
        READ_AFTER_COMMIT.store(true, Ordering::Release);
    }
}

#[no_mangle]
pub extern "C" fn pgmooncake_drop_cstring(cstring: *mut c_char) {
    if !cstring.is_null() {
        unsafe { drop(CString::from_raw(cstring)) }
    }
}

#[no_mangle]
extern "C" fn pgmooncake_get_init_query() -> *mut c_char {
    ATTACH.get().cloned().unwrap_or_default().into_raw()
}

#[no_mangle]
extern "C" fn pgmooncake_get_lsn() -> u64 {
    if READ_AFTER_COMMIT.load(Ordering::Acquire) {
        moonlink_rpc::SOURCE_WATERMARK
    } else {
        0
    }
}
