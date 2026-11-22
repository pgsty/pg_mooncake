use crate::utils::{rpc, DATABASE};
use pgrx::prelude::*;
use std::ffi::{c_int, c_void, CStr};
use std::time::Duration;

static mut PREV_ACCESS: pg_sys::object_access_hook_type = None;

pub(crate) fn init() {
    unsafe {
        PREV_ACCESS = pg_sys::object_access_hook;
        pg_sys::object_access_hook = Some(protect_registry);
    }
}

#[pg_guard]
unsafe extern "C-unwind" fn protect_registry(
    access: pg_sys::ObjectAccessType::Type,
    class: pg_sys::Oid,
    object: pg_sys::Oid,
    sub: c_int,
    arg: *mut c_void,
) {
    if let Some(prev) = PREV_ACCESS {
        prev(access, class, object, sub, arg);
    }
    if access != pg_sys::ObjectAccessType::OAT_DROP
        || class != pg_sys::RelationRelationId
        || sub != 0
    {
        return;
    }
    let name = pg_sys::get_rel_name(object);
    if name.is_null()
        || CStr::from_ptr(name) != c"mirror_registrations"
        || pg_sys::get_rel_namespace(object)
            != pg_sys::get_namespace_oid(c"mooncake".as_ptr(), true)
    {
        return;
    }
    let extension = pg_sys::get_extension_oid(c"pg_mooncake".as_ptr(), true);
    if extension != pg_sys::InvalidOid
        && pg_sys::getExtensionOfObject(class, object) == extension
        && Spi::get_one::<bool>("SELECT EXISTS (SELECT FROM mooncake.mirror_registrations)")
            .expect("checking for mirror registrations")
            == Some(true)
    {
        error!("drop registered mirrors and run SELECT mooncake._reconcile_drops() before removing pg_mooncake");
    }
}

pub(crate) fn registration(name: &str) -> Result<Option<String>, String> {
    let database = DATABASE.clone();
    rpc!(timeout = Duration::from_secs(5); moonlink_rpc::registration, database, name.to_owned())
        .map_err(|err| err.to_string())
}

pub(crate) fn retire(name: &str, generation: &str) -> Result<(), String> {
    let database = DATABASE.clone();
    rpc!(timeout = Duration::from_secs(5); moonlink_rpc::drop_registration,
        database, name.to_owned(), generation.to_owned())
    .map_err(|err| err.to_string())
}

#[pg_extern(sql = false)]
fn mirror_generation(name: &str) -> Option<String> {
    registration(name).unwrap_or_else(|err| error!("cannot identify mirror {name}: {err}"))
}

#[pg_extern(sql = false)]
fn managed_registrations(
) -> TableIterator<'static, (name!(mirror_name, String), name!(generation, String))> {
    let database = DATABASE.clone();
    let rows =
        rpc!(timeout = Duration::from_secs(5); moonlink_rpc::managed_registrations, database)
            .unwrap_or_else(|err| error!("cannot enumerate mirror registrations: {err}"));
    TableIterator::new(rows)
}

#[pg_extern(sql = false)]
fn retire_generation(name: &str, generation: &str) -> bool {
    match retire(name, generation) {
        Ok(()) => true,
        Err(err) => {
            warning!("cleanup of mirror {name} is pending: {err}");
            false
        }
    }
}

pub(crate) fn reconcile() {
    if !unsafe { pg_sys::XactReadOnly || pg_sys::IsInParallelMode() } {
        Spi::run("SELECT mooncake._reconcile_drops()").expect("reconciling committed mirror drops");
    }
}
